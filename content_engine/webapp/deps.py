import time
from pathlib import Path

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates

from content_engine.auth.security import decode_access_token
from content_engine.config import Settings

_bearer_scheme = HTTPBearer(auto_error=False)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Cache-buster for static assets (CSS/JS): fixed for the life of one server
# process, so browsers keep caching normally between requests, but every
# `python dashboard.py` restart (which is when static files actually change
# during development) forces a fresh fetch instead of serving a stale copy.
templates.env.globals["asset_version"] = str(int(time.time()))


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Decodes the Authorization: Bearer <jwt> header. Trusts the role/email
    claims embedded in the token itself (no DB round trip per request) - a
    role change only takes effect on that user's next login."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(settings.jwt_secret_key, credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required for this action")
    return user


def channel_connection_status(settings: Settings, user_id: str) -> list[dict]:
    """Real (not fabricated) connection status per platform. YouTube is now
    per-user (the connected_accounts table) rather than the legacy global
    config/token.json file, which only the CLI still uses. Instagram/TikTok
    remain single shared deployment-wide credentials (set via .env), not yet
    moved to the per-user model."""
    from content_engine.auth import tiktok_oauth
    from content_engine.db import connected_accounts_repo

    youtube_accounts = connected_accounts_repo.list_accounts_public(settings.db_path, user_id, "youtube")

    return [
        {
            "key": "youtube",
            "label": "YouTube",
            "short": "YT",
            "icon_class": "icon-yt",
            "connected": len(youtube_accounts) > 0,
        },
        {
            "key": "instagram",
            "label": "Instagram",
            "short": "IG",
            "icon_class": "icon-ig",
            "connected": bool(settings.instagram_access_token and settings.instagram_business_account_id),
        },
        {
            "key": "tiktok",
            "label": "TikTok",
            "short": "TT",
            "icon_class": "icon-tt",
            "connected": bool(
                settings.tiktok_client_key and tiktok_oauth.load_token(settings.tiktok_token_path)
            ),
        },
    ]
