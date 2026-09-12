from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(days=7)
OAUTH_STATE_TTL = timedelta(minutes=10)
CONNECT_TICKET_TTL = timedelta(minutes=2)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for rows we wrote ourselves) - treat as no match.
        return False


def create_access_token(secret_key: str, user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(secret_key: str, token: str) -> dict:
    """Raises jwt.PyJWTError (expired, bad signature, malformed, ...) on any failure -
    callers translate that into a 401."""
    return jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])


def create_oauth_state_token(secret_key: str, user_id: str) -> str:
    """Short-lived, single-purpose token passed as the OAuth `state` param so
    the callback (which Google redirects to directly, no Authorization header)
    can recover which user initiated the connect flow, and so a state value
    can't be reused as - or forged from - a real session token."""
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "purpose": "oauth_state", "iat": now, "exp": now + OAUTH_STATE_TTL}
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_oauth_state_token(secret_key: str, token: str) -> str:
    """Returns the user_id. Raises jwt.PyJWTError on any failure, or ValueError
    if the token is well-formed but wasn't issued for this purpose."""
    payload = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    if payload.get("purpose") != "oauth_state":
        raise ValueError("Not an OAuth state token")
    return payload["sub"]


def create_connect_ticket_token(secret_key: str, user_id: str) -> str:
    """Short-lived, single-purpose token for GET /oauth/youtube/connect - that
    endpoint is a full browser navigation (Google's consent screen redirects
    the user's browser there directly), so it can't receive an Authorization
    header the way a fetch() call would, and the query string is the only
    place to put anything. Using the real 7-day session JWT there would put a
    long-lived, full-access credential in server access logs, browser history,
    and any Referer header - this ticket is scoped to only this one purpose
    and expires in minutes, so a leaked copy is far less useful."""
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "purpose": "connect_ticket", "iat": now, "exp": now + CONNECT_TICKET_TTL}
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_connect_ticket_token(secret_key: str, token: str) -> str:
    """Returns the user_id. Raises jwt.PyJWTError on any failure, or ValueError
    if the token is well-formed but wasn't issued for this purpose."""
    payload = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    if payload.get("purpose") != "connect_ticket":
        raise ValueError("Not a connect ticket token")
    return payload["sub"]
