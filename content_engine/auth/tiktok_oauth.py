import json
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from content_engine.config import Settings
from content_engine.errors import UploadFailedError

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPE = "video.publish"


def build_authorization_url(client_key: str, redirect_uri: str, state: str = "content-engine") -> str:
    params = {
        "client_key": client_key,
        "scope": SCOPE,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(client_key: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as e:
        raise UploadFailedError(f"TikTok token exchange request failed: {e}") from e

    data = response.json()
    if response.status_code != 200 or "access_token" not in data:
        raise UploadFailedError(f"TikTok token exchange failed: {data}")
    return data


def _refresh(client_key: str, client_secret: str, refresh_token_value: str) -> dict:
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token_value,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as e:
        raise UploadFailedError(f"TikTok token refresh request failed: {e}") from e

    data = response.json()
    if response.status_code != 200 or "access_token" not in data:
        raise UploadFailedError(f"TikTok token refresh failed: {data}")
    return data


def save_token(token_path: Path, token_data: dict) -> None:
    token_data = dict(token_data)
    token_data["_saved_at"] = time.time()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(token_data), encoding="utf-8")


def load_token(token_path: Path) -> dict | None:
    if not token_path.exists():
        return None
    return json.loads(token_path.read_text(encoding="utf-8"))


def get_access_token(settings: Settings) -> str:
    """Returns a valid access token, refreshing the cached one if it's about to expire.

    Raises UploadFailedError (not ConfigError) for any misconfiguration/missing-auth
    case, since this is called from inside TikTokUploader.upload() and the pipeline's
    per-platform error handling only catches UploadFailedError - a ConfigError here
    would incorrectly abort the whole multi-platform run instead of just this platform.
    """
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise UploadFailedError("TikTok is not configured: set TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET in .env")

    token = load_token(settings.tiktok_token_path)
    if token is None:
        raise UploadFailedError(
            f"No cached TikTok token at {settings.tiktok_token_path}. "
            "Run `python run.py --tiktok-auth <redirect_uri>` once to authorize."
        )

    saved_at = token.get("_saved_at", 0)
    expires_in = token.get("expires_in", 0)
    if time.time() < saved_at + expires_in - 60:
        return token["access_token"]

    refreshed = _refresh(settings.tiktok_client_key, settings.tiktok_client_secret, token["refresh_token"])
    save_token(settings.tiktok_token_path, refreshed)
    return refreshed["access_token"]
