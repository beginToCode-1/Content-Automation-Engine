import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from content_engine.auth.security import create_access_token, hash_password, verify_password
from content_engine.config import Settings
from content_engine.db import users_repo
from content_engine.webapp.deps import get_current_user, get_settings

router = APIRouter(prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
async def register(payload: RegisterRequest, settings: Settings = Depends(get_settings)):
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
        user = users_repo.create_user_with_bootstrap_role(settings.db_path, email, password_hash)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    return _issue_token(settings, user["id"], user["email"], user["role"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, settings: Settings = Depends(get_settings)):
    email = payload.email.strip().lower()
    user = users_repo.get_user_by_email(settings.db_path, email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return _issue_token(settings, user["id"], user["email"], user["role"])


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)
