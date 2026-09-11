from unittest.mock import patch

from content_engine.models import PlatformUploadOutcome, UploadResult
from content_engine.notifications.dispatch import notify_upload_outcome
from tests.test_pipeline_progress_callback import _fake_settings


def test_notify_upload_outcome_noops_when_notifications_disabled(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.notifications_enabled = False
    outcome = PlatformUploadOutcome(
        platform="youtube",
        result=UploadResult(video_id="v1", url="https://youtube.com/shorts/v1", privacy_status="private"),
    )

    with patch("content_engine.notifications.dispatch.send_desktop_notification") as mock_desktop, patch(
        "content_engine.notifications.dispatch.send_email_notification"
    ) as mock_email:
        notify_upload_outcome(settings, "topic", "label", "youtube", outcome, "run1")

    mock_desktop.assert_not_called()
    mock_email.assert_not_called()


def test_notify_upload_outcome_fires_both_channels_when_enabled(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.notifications_enabled = True
    settings.notify_desktop_enabled = True
    settings.notify_email_enabled = True
    outcome = PlatformUploadOutcome(
        platform="youtube",
        result=UploadResult(video_id="v1", url="https://youtube.com/shorts/v1", privacy_status="private"),
    )

    with patch("content_engine.notifications.dispatch.send_desktop_notification") as mock_desktop, patch(
        "content_engine.notifications.dispatch.send_email_notification"
    ) as mock_email:
        notify_upload_outcome(settings, "topic", "label", "youtube", outcome, "run1")

    mock_desktop.assert_called_once()
    mock_email.assert_called_once()


def test_notify_upload_outcome_respects_per_channel_toggles(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.notifications_enabled = True
    settings.notify_desktop_enabled = False
    settings.notify_email_enabled = True
    outcome = PlatformUploadOutcome(platform="youtube", result=None, error="boom")

    with patch("content_engine.notifications.dispatch.send_desktop_notification") as mock_desktop, patch(
        "content_engine.notifications.dispatch.send_email_notification"
    ) as mock_email:
        notify_upload_outcome(settings, "topic", "label", "youtube", outcome, "run1")

    mock_desktop.assert_not_called()
    mock_email.assert_called_once()
