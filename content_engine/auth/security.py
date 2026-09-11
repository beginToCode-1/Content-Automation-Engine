from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(days=7)


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
