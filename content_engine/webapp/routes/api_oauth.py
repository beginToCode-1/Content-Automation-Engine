import hmac
import logging
import secrets
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from psycopg_pool import ConnectionPool

from content_engine.auth import google_oauth
from content_engine.auth.security import (
    create_connect_ticket_token,
    create_oauth_state_token,
    decode_connect_ticket_token,
    decode_oauth_state_token,
)
from content_engine.config import Settings
from content_engine.db import connected_accounts_repo
from content_engine.errors import ConfigError
from content_engine.webapp.deps import get_current_user, get_db_pool, get_settings

logger = logging.getLogger("content_engine.webapp.routes.api_oauth")

router = APIRouter(prefix="/api")

# Binds the Google consent flow to the browser that started it (see the callback).
_NONCE_COOKIE = "yt_oauth_nonce"
_NONCE_COOKIE_PATH = "/api/oauth/youtube"


def _frontend_redirect(settings: Settings, path: str) -> str:
    base = settings.frontend_base_url or ""
    return f"{base}{path}"


@router.post("/oauth/youtube/connect-ticket")
def create_connect_ticket(
    settings: Settings = Depends(get_settings), user: dict = Depends(get_current_user)
):
    """Issues a short-lived (2 minute), single-purpose ticket for the frontend
    to pass to GET /oauth/youtube/connect below, minted via a normal
    authenticated fetch() (Authorization header) - so the long-lived 7-day
    session JWT itself never has to appear in a URL, server access logs, or
    browser history."""
    ticket = create_connect_ticket_token(settings.jwt_secret_key, user["id"])
    return {"ticket": ticket}


@router.get("/oauth/youtube/connect")
def connect_youtube(
    ticket: str = Query(..., description="A short-lived connect ticket from POST "
    "/oauth/youtube/connect-ticket, passed as a query param since this endpoint is a full browser "
    "navigation (Google redirects the user's browser here directly, so there's no way to attach an "
    "Authorization header the way a fetch() call would)."),
    settings: Settings = Depends(get_settings),
):
    try:
        user_id = decode_connect_ticket_token(settings.jwt_secret_key, ticket)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired ticket")

    nonce = secrets.token_urlsafe(32)
    try:
        state = create_oauth_state_token(settings.jwt_secret_key, user_id, nonce)
        auth_url = google_oauth.build_web_auth_url(settings, state)
    except ConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))

    response = RedirectResponse(auth_url, status_code=302)
    # SameSite=Lax still sends the cookie on Google's top-level redirect back to
    # the callback, which lives on this same backend origin.
    response.set_cookie(
        _NONCE_COOKIE,
        nonce,
        max_age=600,
        path=_NONCE_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=(settings.google_oauth_redirect_uri or "").startswith("https://"),
    )
    return response


@router.get("/oauth/youtube/callback")
def youtube_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    nonce_cookie: str | None = Cookie(None, alias=_NONCE_COOKIE),
    settings: Settings = Depends(get_settings),
    pool: ConnectionPool = Depends(get_db_pool),
):
    if error:
        # quote(): the provider's value must not be able to add its own query params.
        return RedirectResponse(_frontend_redirect(settings, f"/accounts?error={quote(error, safe='')}"), status_code=302)
    if not code or not state:
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=missing_code"), status_code=302)

    try:
        user_id, nonce = decode_oauth_state_token(settings.jwt_secret_key, state)
    except (jwt.PyJWTError, ValueError):
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=invalid_state"), status_code=302)
    # Without this check, a consent link started by one user could be forwarded to
    # someone else, whose channel would then be saved under the first user's account.
    if not nonce_cookie or not hmac.compare_digest(nonce_cookie, nonce):
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=invalid_state"), status_code=302)

    try:
        creds = google_oauth.exchange_code_for_credentials(settings, code)
        channel_id, channel_title = google_oauth.fetch_channel_info(creds)
    except Exception:
        logger.exception("YouTube connect failed for user_id=%s", user_id)
        return RedirectResponse(_frontend_redirect(settings, "/accounts?error=connect_failed"), status_code=302)

    connected_accounts_repo.upsert_account(
        pool,
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

    response = RedirectResponse(_frontend_redirect(settings, "/accounts?connected=youtube"), status_code=302)
    response.delete_cookie(_NONCE_COOKIE, path=_NONCE_COOKIE_PATH)  # one use only
    return response


@router.get("/accounts")
def list_accounts(pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(get_current_user)):
    return {"accounts": connected_accounts_repo.list_accounts_public(pool, user["id"])}


@router.delete("/accounts/{account_id}")
def disconnect_account(
    account_id: str, pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(get_current_user)
):
    try:
        deleted = connected_accounts_repo.delete_account(pool, account_id, user["id"])
    except connected_accounts_repo.AccountInUseError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Connected account not found")
    return {"deleted": True}
