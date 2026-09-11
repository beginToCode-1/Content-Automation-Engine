import time
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from content_engine.config import Settings

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Cache-buster for static assets (CSS/JS): fixed for the life of one server
# process, so browsers keep caching normally between requests, but every
# `python dashboard.py` restart (which is when static files actually change
# during development) forces a fresh fetch instead of serving a stale copy.
templates.env.globals["asset_version"] = str(int(time.time()))


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def channel_connection_status(settings: Settings) -> list[dict]:
    """Real (not fabricated) connection status per platform, derived from
    whatever credentials are actually present on disk/in .env - no follower
    counts or fake sync state, just whether each platform is actually usable."""
    from content_engine.auth import tiktok_oauth

    return [
        {
            "key": "youtube",
            "label": "YouTube",
            "short": "YT",
            "icon_class": "icon-yt",
            "connected": settings.token_path.exists(),
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
