import logging
import smtplib
from email.message import EmailMessage

from content_engine.config import Settings

logger = logging.getLogger("content_engine.notifications.email")


def send_email_notification(subject: str, body: str, settings: Settings) -> bool:
    """Sends a plain-text email via SMTP (stdlib only, no new dependency).
    Never raises - any failure (missing config, auth, connection) is caught and
    logged, returning False."""
    if not settings.notify_email_to or not settings.smtp_username or not settings.smtp_password:
        logger.warning("Email notification skipped: SMTP not fully configured")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address or settings.smtp_username
    message["To"] = settings.notify_email_to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send email notification")
        return False
