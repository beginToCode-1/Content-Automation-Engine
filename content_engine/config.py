import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from content_engine.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    gemini_api_key: str
    gemini_model: str
    youtube_api_key: str | None
    upload_privacy_status: str
    work_dir: Path
    client_secret_path: Path
    token_path: Path

    dashboard_host: str
    dashboard_port: int
    dashboard_max_workers: int
    db_path: Path
    scheduler_poll_interval_s: int

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

    cors_allow_origins: list[str] = field(default_factory=list)

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

        work_dir = PROJECT_ROOT / os.getenv("WORK_DIR", "work")
        work_dir.mkdir(parents=True, exist_ok=True)

        client_secret_path = PROJECT_ROOT / "config" / "client_secret.json"
        token_path = PROJECT_ROOT / "config" / "token.json"
        tiktok_token_path = PROJECT_ROOT / "config" / "tiktok_token.json"

        db_path = PROJECT_ROOT / os.getenv("DB_PATH", "content_engine.db")

        jwt_secret_key = os.getenv("JWT_SECRET_KEY", "").strip()
        if not jwt_secret_key:
            raise ConfigError(
                "JWT_SECRET_KEY is not set. Generate one with "
                "`python -c \"import secrets; print(secrets.token_hex(32))\"` and add it to .env."
            )

        return cls(
            gemini_api_key=gemini_api_key,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip(),
            youtube_api_key=(os.getenv("YOUTUBE_API_KEY", "").strip() or None),
            upload_privacy_status=privacy_status,
            work_dir=work_dir,
            client_secret_path=client_secret_path,
            token_path=token_path,
            # Railway/Render inject PORT and expect the app to bind 0.0.0.0 to it;
            # DASHBOARD_HOST/DASHBOARD_PORT still win if explicitly set, for local use.
            dashboard_host=os.getenv("DASHBOARD_HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1").strip(),
            dashboard_port=int(os.getenv("DASHBOARD_PORT") or os.getenv("PORT", "8000")),
            dashboard_max_workers=int(os.getenv("DASHBOARD_MAX_WORKERS", "2")),
            db_path=db_path,
            scheduler_poll_interval_s=int(os.getenv("SCHEDULER_POLL_INTERVAL_S", "30")),
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
            batch_default_stagger_minutes=int(os.getenv("BATCH_DEFAULT_STAGGER_MINUTES", "180")),
            batch_max_videos=int(os.getenv("BATCH_MAX_VIDEOS", "5")),
            batch_max_clips_per_video=int(os.getenv("BATCH_MAX_CLIPS_PER_VIDEO", "5")),
            notifications_enabled=os.getenv("NOTIFICATIONS_ENABLED", "false").strip().lower() == "true",
            notify_desktop_enabled=os.getenv("NOTIFY_DESKTOP_ENABLED", "true").strip().lower() == "true",
            notify_email_enabled=os.getenv("NOTIFY_EMAIL_ENABLED", "true").strip().lower() == "true",
            notify_email_to=(os.getenv("NOTIFY_EMAIL_TO", "").strip() or None),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=(os.getenv("SMTP_USERNAME", "").strip() or None),
            smtp_password=(os.getenv("SMTP_PASSWORD", "").strip() or None),
            smtp_from_address=(os.getenv("SMTP_FROM_ADDRESS", "").strip() or None),
            jwt_secret_key=jwt_secret_key,
        )
