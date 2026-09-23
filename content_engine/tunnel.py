"""Optional automatic ngrok tunnel management, for local dev only.

Instagram's Graph API and TikTok's OAuth redirect both need a public HTTPS
URL pointed at this machine's local dashboard server. Previously that meant
running `ngrok http 8000` by hand in a second terminal and pasting the
resulting URL into .env / the TikTok developer dashboard every time. This
module starts that tunnel automatically instead, when opted into via
NGROK_AUTHTOKEN.

Deliberately NOT started when a `PORT` env var is present (Render/Railway
inject it) - a deployed server already has a real public URL, and tunneling
one would be actively wrong, not just unnecessary.

Instagram uploads can use the live tunnel URL transparently (see
InstagramUploader) because Instagram fetches the video from a URL at upload
time - a fresh random ngrok URL on every restart is fine there. TikTok's
OAuth redirect URI must be pre-registered in TikTok's developer dashboard,
so without a paid reserved ngrok domain, a changed URL still needs a manual
update there - this module only saves the user from separately running
`ngrok` themselves; see run.py's tiktok_auth() for that flow.
"""

import logging
import os

logger = logging.getLogger("content_engine.tunnel")

_public_url: str | None = None


def should_start_tunnel() -> bool:
    """Opt-in via NGROK_AUTHTOKEN, and only for local dev (no PORT env var -
    Render/Railway inject that for deployed services)."""
    return bool(os.getenv("NGROK_AUTHTOKEN", "").strip()) and not os.getenv("PORT")


def start_tunnel(port: int) -> str | None:
    """Starts an ngrok tunnel to localhost:port if NGROK_AUTHTOKEN is set and
    this isn't a deployed (PORT-injected) environment. Returns the public
    HTTPS URL, or None if not started. Safe to call more than once - a second
    call is a no-op that returns the already-active URL."""
    global _public_url
    if _public_url is not None:
        return _public_url
    if not should_start_tunnel():
        return None

    try:
        from pyngrok import ngrok
    except ImportError:
        logger.warning("NGROK_AUTHTOKEN is set but pyngrok is not installed - run `pip install pyngrok`")
        return None

    try:
        ngrok.set_auth_token(os.getenv("NGROK_AUTHTOKEN", "").strip())
        tunnel_obj = ngrok.connect(port, "http")
        _public_url = tunnel_obj.public_url.replace("http://", "https://")
        logger.info("ngrok tunnel started: %s -> localhost:%s", _public_url, port)
        return _public_url
    except Exception:
        logger.exception("Failed to start ngrok tunnel - continuing without one")
        return None


def stop_tunnel() -> None:
    global _public_url
    if _public_url is None:
        return
    try:
        from pyngrok import ngrok

        ngrok.kill()
    except Exception:
        logger.exception("Failed to stop ngrok tunnel cleanly (ignored)")
    finally:
        _public_url = None


def get_public_url() -> str | None:
    """The live tunnel URL, if one is running - checked as a fallback by
    InstagramUploader when INSTAGRAM_PUBLIC_VIDEO_BASE_URL isn't explicitly
    set. Not baked into Settings at process boot, since the tunnel starts
    asynchronously during FastAPI's lifespan startup, after Settings.load()
    has already run."""
    return _public_url
