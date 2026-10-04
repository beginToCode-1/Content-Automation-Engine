import re
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from content_engine.auth.security import create_access_token, hash_password, verify_password
from content_engine.config import Settings
from content_engine.db import users_repo
from content_engine.webapp.deps import get_current_user, get_db_pool, get_settings

router = APIRouter(prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Slows password guessing: after this many wrong passwords for one email within
# the window, logins for that email are refused until the oldest failure ages out.
# ponytail: in-memory, per process (this app runs one) - resets on restart;
# move to the database if the backend ever runs more than one instance.
_MAX_FAILED_LOGINS = 10
_FAILED_LOGIN_WINDOW_S = 15 * 60
_failed_logins: dict[str, deque] = defaultdict(deque)
_failed_logins_lock = threading.Lock()


def _recent_failures(email: str, now: float) -> deque:
    failures = _failed_logins[email]
    while failures and now - failures[0] > _FAILED_LOGIN_WINDOW_S:
        failures.popleft()
    return failures


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _issue_token(settings: Settings, user_id: str, email: str, role: str) -> TokenResponse:
    token = create_access_token(settings.jwt_secret_key, user_id, email, role)
    return TokenResponse(access_token=token, user=UserOut(id=user_id, email=email, role=role))


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: RegisterRequest,
    settings: Settings = Depends(get_settings),
    pool: ConnectionPool = Depends(get_db_pool),
):
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    # bcrypt's limit is 72 *bytes*, not characters - a password within 72
    # characters can still exceed 72 bytes once multi-byte UTF-8 characters
    # are involved, which either silently truncates or raises inside bcrypt
    # depending on the installed build.
    password_bytes = payload.password.encode("utf-8")
    if not (8 <= len(password_bytes) <= 72):
        raise HTTPException(status_code=400, detail="Password must be 8-72 characters")

    # First account ever created on this deployment becomes admin; everyone
    # after that defaults to viewer. There is no invite/promotion flow yet -
    # an existing admin has to be promoted directly in the database.
    password_hash = hash_password(payload.password)

    try:
        user = users_repo.create_user_with_bootstrap_role(pool, email, password_hash)
    except users_repo.DuplicateEmailError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    return _issue_token(settings, user["id"], user["email"], user["role"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    settings: Settings = Depends(get_settings),
    pool: ConnectionPool = Depends(get_db_pool),
):
    email = payload.email.strip().lower()
    with _failed_logins_lock:
        if len(_recent_failures(email, time.monotonic())) >= _MAX_FAILED_LOGINS:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = users_repo.get_user_by_email(pool, email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        with _failed_logins_lock:
            _recent_failures(email, time.monotonic()).append(time.monotonic())
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    with _failed_logins_lock:
        _failed_logins.pop(email, None)

    return _issue_token(settings, user["id"], user["email"], user["role"])


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)
