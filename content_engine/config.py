import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from content_engine.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parent.parent



_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    """Accepts 1/0, true/false, yes/no, on/off. Blank means the default; anything
    else is an error rather than silently meaning False."""
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None

@dataclass
class Settings:
    gemini_api_key: str
    gemini_model: str
    youtube_api_key: str | None
    upload_privacy_status: str
    log_level: str
    work_dir: Path
    client_secret_path: Path
    token_path: Path

    dashboard_host: str
    dashboard_port: int
    dashboard_max_workers: int
    database_url: str
    scheduler_poll_interval_s: int

    upload_max_retries: int
    upload_retry_backoff_base_s: float

    instagram_access_token: str | None
    instagram_business_account_id: str | None
    instagram_graph_api_version: str
    instagram_public_video_base_url: str | None

    tiktok_client_key: str | None
    tiktok_client_secret: str | None
    tiktok_token_path: Path

    batch_default_stagger_minutes: int
    batch_max_videos: int
    batch_max_clips_per_video: int

    notifications_enabled: bool
    notify_desktop_enabled: bool
    notify_email_enabled: bool
    notify_email_to: str | None
    smtp_host: str
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from_address: str | None

    jwt_secret_key: str = ""
    token_encryption_key: str = ""

    # Web-flow (per-user, multi-account) Google OAuth client - distinct from
    # client_secret_path/token_path above, which are the legacy Desktop-app
    # client used only by the CLI's single global account. None of these three
    # are required at startup (unlike jwt_secret_key/token_encryption_key):
    # the "Connect YouTube" flow just 400s with a clear message until they're
    # set, so the rest of the app keeps working without them configured yet.
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None

    # Where /api/oauth/youtube/callback sends the browser after a connect
    # attempt finishes (success or failure) - the deployed frontend's origin.
    frontend_base_url: str | None = None

    cors_allow_origins: list[str] = field(default_factory=list)

    # Only search Creative Commons videos, which their creators allow to be
    # reused. Far fewer results, but far less risk of copyright claims.
    youtube_creative_commons_only: bool = False

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")

        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not gemini_api_key:
            raise ConfigError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
            )

        privacy_status = os.getenv("UPLOAD_PRIVACY_STATUS", "private").strip().lower()
        if privacy_status not in {"private", "unlisted", "public"}:
            raise ConfigError(
                f"UPLOAD_PRIVACY_STATUS must be one of private/unlisted/public, got {privacy_status!r}"
            )

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigError(
                f"LOG_LEVEL must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL, got {log_level!r}"
            )

        work_dir = PROJECT_ROOT / os.getenv("WORK_DIR", "work")
        work_dir.mkdir(parents=True, exist_ok=True)

        client_secret_path = PROJECT_ROOT / "config" / "client_secret.json"
        token_path = PROJECT_ROOT / "config" / "token.json"
        tiktok_token_path = PROJECT_ROOT / "config" / "tiktok_token.json"

        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise ConfigError(
                "DATABASE_URL is not set. Point it at a Postgres connection string "
                "(e.g. Supabase's Session pooler URI) - see .env.example."
            )

        jwt_secret_key = os.getenv("JWT_SECRET_KEY", "").strip()
        if not jwt_secret_key:
            raise ConfigError(
                "JWT_SECRET_KEY is not set. Generate one with "
                "`python -c \"import secrets; print(secrets.token_hex(32))\"` and add it to .env."
            )

        token_encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
        if not token_encryption_key:
            raise ConfigError(
                "TOKEN_ENCRYPTION_KEY is not set. Generate one with "
                "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
                "and add it to .env."
            )

        return cls(
            gemini_api_key=gemini_api_key,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip(),
            youtube_api_key=(os.getenv("YOUTUBE_API_KEY", "").strip() or None),
            upload_privacy_status=privacy_status,
            log_level=log_level,
            work_dir=work_dir,
            client_secret_path=client_secret_path,
            token_path=token_path,
            # Railway/Render inject PORT and expect the app to bind 0.0.0.0 to it;
            # DASHBOARD_HOST/DASHBOARD_PORT still win if explicitly set, for local use.
            dashboard_host=os.getenv("DASHBOARD_HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1").strip(),
            dashboard_port=_env_int("DASHBOARD_PORT", _env_int("PORT", 8000)),
            dashboard_max_workers=_env_int("DASHBOARD_MAX_WORKERS", 2),
            database_url=database_url,
            scheduler_poll_interval_s=_env_int("SCHEDULER_POLL_INTERVAL_S", 30),
            upload_max_retries=_env_int("UPLOAD_MAX_RETRIES", 3),
            upload_retry_backoff_base_s=_env_float("UPLOAD_RETRY_BACKOFF_BASE_S", 2),
            cors_allow_origins=[
                origin.strip()
                for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
                if origin.strip()
            ],
            instagram_access_token=(os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip() or None),
            instagram_business_account_id=(
                os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip() or None
            ),
            instagram_graph_api_version=os.getenv("INSTAGRAM_GRAPH_API_VERSION", "v21.0").strip(),
            instagram_public_video_base_url=(
                os.getenv("INSTAGRAM_PUBLIC_VIDEO_BASE_URL", "").strip().rstrip("/") or None
            ),
            tiktok_client_key=(os.getenv("TIKTOK_CLIENT_KEY", "").strip() or None),
            tiktok_client_secret=(os.getenv("TIKTOK_CLIENT_SECRET", "").strip() or None),
            tiktok_token_path=tiktok_token_path,
            batch_default_stagger_minutes=_env_int("BATCH_DEFAULT_STAGGER_MINUTES", 180),
            batch_max_videos=_env_int("BATCH_MAX_VIDEOS", 5),
            batch_max_clips_per_video=_env_int("BATCH_MAX_CLIPS_PER_VIDEO", 5),
            notifications_enabled=_env_bool("NOTIFICATIONS_ENABLED", False),
            notify_desktop_enabled=_env_bool("NOTIFY_DESKTOP_ENABLED", True),
            notify_email_enabled=_env_bool("NOTIFY_EMAIL_ENABLED", True),
            notify_email_to=(os.getenv("NOTIFY_EMAIL_TO", "").strip() or None),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
            smtp_port=_env_int("SMTP_PORT", 587),
            smtp_username=(os.getenv("SMTP_USERNAME", "").strip() or None),
            smtp_password=(os.getenv("SMTP_PASSWORD", "").strip() or None),
            smtp_from_address=(os.getenv("SMTP_FROM_ADDRESS", "").strip() or None),
            jwt_secret_key=jwt_secret_key,
            token_encryption_key=token_encryption_key,
            google_oauth_client_id=(os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip() or None),
            google_oauth_client_secret=(os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip() or None),
            google_oauth_redirect_uri=(os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip() or None),
            frontend_base_url=(os.getenv("FRONTEND_BASE_URL", "").strip().rstrip("/") or None),
            youtube_creative_commons_only=_env_bool("YOUTUBE_CREATIVE_COMMONS_ONLY", False),
        )
