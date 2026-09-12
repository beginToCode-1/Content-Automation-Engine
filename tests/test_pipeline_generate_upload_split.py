from unittest.mock import MagicMock, patch

import pytest

from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata, UploadResult
from content_engine.pipeline import upload_clip_to_platforms
from tests.test_pipeline_progress_callback import _fake_settings


def test_upload_clip_to_platforms_single_failure_raises(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below
    uploader_instance = MagicMock()
    uploader_instance.upload.side_effect = UploadFailedError("quota exceeded")

    with patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=uploader_instance),
    ):
        with pytest.raises(UploadFailedError):
            upload_clip_to_platforms(
                tmp_path / "clip.mp4",
                ClipMetadata(title="t", description="d"),
                ["youtube"],
                settings,
                "private",
                "topic",
                "run123",
            )


def test_upload_clip_to_platforms_partial_success_does_not_raise(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below
    youtube_instance = MagicMock()
    youtube_instance.upload.return_value = UploadResult(
        video_id="yt1", url="https://youtube.com/shorts/yt1", privacy_status="private"
    )
    tiktok_instance = MagicMock()
    tiktok_instance.upload.side_effect = UploadFailedError("not authorized")

    with patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=youtube_instance),
        TikTokUploader=MagicMock(return_value=tiktok_instance),
    ):
        outcomes = upload_clip_to_platforms(
            tmp_path / "clip.mp4",
            ClipMetadata(title="t", description="d"),
            ["youtube", "tiktok"],
            settings,
            "private",
            "topic",
            "run123",
        )

    outcomes_by_platform = {o.platform: o for o in outcomes}
    assert outcomes_by_platform["youtube"].result.video_id == "yt1"
    assert outcomes_by_platform["tiktok"].error == "not authorized"


def test_upload_clip_to_platforms_uses_given_privacy_verbatim(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below
    uploader_instance = MagicMock()
    uploader_instance.upload.return_value = UploadResult(
        video_id="yt1", url="https://youtube.com/shorts/yt1", privacy_status="public"
    )

    with patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=uploader_instance),
    ):
        upload_clip_to_platforms(
            tmp_path / "clip.mp4",
            ClipMetadata(title="t", description="d"),
            ["youtube"],
            settings,
            "public",
            "topic",
            "run123",
        )

    assert uploader_instance.upload.call_args.args[2] == "public"


def test_upload_clip_to_platforms_fires_notification_when_enabled(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below
    settings.notifications_enabled = True
    uploader_instance = MagicMock()
    uploader_instance.upload.return_value = UploadResult(
        video_id="yt1", url="https://youtube.com/shorts/yt1", privacy_status="private"
    )

    with patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=uploader_instance),
    ), patch("content_engine.pipeline.notify_upload_outcome") as mock_notify:
        upload_clip_to_platforms(
            tmp_path / "clip.mp4",
            ClipMetadata(title="t", description="d"),
            ["youtube"],
            settings,
            "private",
            "my topic",
            "run123",
        )

    mock_notify.assert_called_once()
    args = mock_notify.call_args.args
    assert args[1] == "my topic"
    assert args[3] == "youtube"
