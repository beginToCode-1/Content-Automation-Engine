import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from content_engine.auth import google_oauth
from content_engine.auth.security import create_oauth_state_token, decode_access_token, decode_oauth_state_token
from content_engine.config import Settings
from content_engine.db import connected_accounts_repo
from content_engine.errors import ConfigError
from content_engine.webapp.deps import get_current_user, get_settings

logger = logging.getLogger("content_engine.webapp.routes.api_oauth")

router = APIRouter(prefix="/api")


def _frontend_redirect(settings: Settings, path: str) -> str:
    base = settings.frontend_base_url or ""
    return f"{base}{path}"


@router.get("/oauth/youtube/connect")
async def connect_youtube(
    token: str = Query(..., description="A normal session JWT, passed as a query param since this "
    "endpoint is a full browser navigation (Google redirects the user's browser here directly, so "
    "there's no way to attach an Authorization header the way a fetch() call would)."),
    settings: Settings = Depends(get_settings),
):
    try:
        payload = decode_access_token(settings.jwt_secret_key, token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload["sub"]

    try:
        state = create_oauth_state_token(settings.jwt_secret_key, user_id)
        auth_url = google_oauth.build_web_auth_url(settings, state)
    except ConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return RedirectResponse(auth_url, status_code=302)


@router.get("/oauth/youtube/callback")
async def youtube_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Settings = Depends(get_settings),
):
    if error:
        return RedirectResponse(_frontend_redirect(settings, f"/accounts?error={error}"), status_code=302)
    if not code or not state:
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=missing_code"), status_code=302)

    try:
        user_id = decode_oauth_state_token(settings.jwt_secret_key, state)
    except (jwt.PyJWTError, ValueError):
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=invalid_state"), status_code=302)

    try:
        creds = google_oauth.exchange_code_for_credentials(settings, code)
        channel_id, channel_title = google_oauth.fetch_channel_info(creds)
    except Exception:
        logger.exception("YouTube connect failed for user_id=%s", user_id)
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=connect_failed"), status_code=302)

    connected_accounts_repo.upsert_account(
        settings.db_path,
        settings.token_encryption_key,
        user_id=user_id,
        platform="youtube",
        account_label=channel_title,
        external_account_id=channel_id,
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        token_expiry=google_oauth.expiry_to_iso(creds),
        scopes=list(creds.scopes or []),
    )

    return RedirectResponse(_frontend_redirect(settings, "/accounts?connected=youtube"), status_code=302)


@router.get("/accounts")
async def list_accounts(settings: Settings = Depends(get_settings), user: dict = Depends(get_current_user)):
    return {"accounts": connected_accounts_repo.list_accounts_public(settings.db_path, user["id"])}


@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: str, settings: Settings = Depends(get_settings), user: dict = Depends(get_current_user)
):
    deleted = connected_accounts_repo.delete_account(settings.db_path, account_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Connected account not found")
    return {"deleted": True}
