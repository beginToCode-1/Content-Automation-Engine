from unittest.mock import MagicMock, patch

from content_engine.notifications.email import send_email_notification
from tests.test_pipeline_progress_callback import _fake_settings


def _configured_settings(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.notify_email_to = "recipient@example.com"
    settings.smtp_username = "sender@gmail.com"
    settings.smtp_password = "app-password"
    settings.smtp_from_address = "sender@gmail.com"
    return settings


def test_send_email_notification_success(tmp_path):
    settings = _configured_settings(tmp_path)
    mock_server = MagicMock()

    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value = mock_server
        result = send_email_notification("subject", "body", settings)

    assert result is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("sender@gmail.com", "app-password")
    mock_server.send_message.assert_called_once()


def test_send_email_notification_skips_when_not_configured(tmp_path):
    settings = _fake_settings(tmp_path)  # notify_email_to/smtp_username/password left None

    with patch("smtplib.SMTP") as mock_smtp:
        result = send_email_notification("subject", "body", settings)

    assert result is False
    mock_smtp.assert_not_called()


def test_send_email_notification_never_raises_on_smtp_failure(tmp_path):
    settings = _configured_settings(tmp_path)

    with patch("smtplib.SMTP", side_effect=OSError("connection refused")):
        result = send_email_notification("subject", "body", settings)

    assert result is False
