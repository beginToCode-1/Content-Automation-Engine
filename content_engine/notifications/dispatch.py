from content_engine.config import Settings
from content_engine.models import PlatformUploadOutcome
from content_engine.notifications.desktop import send_desktop_notification
from content_engine.notifications.email import send_email_notification


def notify_upload_outcome(
    settings: Settings,
    topic: str,
    label: str,
    platform: str,
    outcome: PlatformUploadOutcome,
    run_id: str,
) -> None:
    """Single entry point for upload-completion notifications. No-ops entirely
    unless settings.notifications_enabled is True. When enabled, fires whichever
    of desktop/email are individually toggled on - each wrapped so one channel's
    failure never affects the other or the calling upload."""
    if not settings.notifications_enabled:
        return

    if outcome.result:
        title = f"Uploaded to {platform}"
        body = f'"{label}" is live on {platform}.\n{outcome.result.url}\nPrivacy: {outcome.result.privacy_status}'
    else:
        title = f"Upload to {platform} failed"
        body = f'"{label}" failed to upload to {platform}.\n{outcome.error}'

    if settings.notify_desktop_enabled:
        send_desktop_notification(title, body)
    if settings.notify_email_enabled:
        send_email_notification(f"Content Engine: {title}", f"Topic: {topic}\nRun: {run_id}\n\n{body}", settings)
