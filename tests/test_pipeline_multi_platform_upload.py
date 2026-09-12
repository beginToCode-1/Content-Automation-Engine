from unittest.mock import MagicMock, patch

import pytest

from content_engine.errors import UploadFailedError
from content_engine.models import UploadResult
from content_engine.pipeline import run_pipeline
from tests.test_pipeline_progress_callback import _fake_settings, _patch_stages


def _patch_youtube_only(upload_side_effect):
    uploader_instance = MagicMock()
    uploader_instance.upload.side_effect = upload_side_effect
    return patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=uploader_instance),
    )


def test_single_platform_failure_raises_upload_failed_error(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below

    with _patch_stages(tmp_path), _patch_youtube_only(UploadFailedError("quota exceeded")):
        with pytest.raises(UploadFailedError):
            run_pipeline("stoic philosophy", settings, dry_run=False, target_platforms=["youtube"])


def test_multi_platform_partial_success_does_not_raise(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below

    youtube_instance = MagicMock()
    youtube_instance.upload.return_value = UploadResult(
        video_id="yt123", url="https://youtube.com/shorts/yt123", privacy_status="private"
    )
    tiktok_instance = MagicMock()
    tiktok_instance.upload.side_effect = UploadFailedError("tiktok account not authorized")

    with _patch_stages(tmp_path), patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=youtube_instance),
        TikTokUploader=MagicMock(return_value=tiktok_instance),
    ):
        result = run_pipeline(
            "stoic philosophy", settings, dry_run=False, target_platforms=["youtube", "tiktok"]
        )

    outcomes = {o.platform: o for o in result.uploads}
    assert outcomes["youtube"].result.video_id == "yt123"
    assert outcomes["tiktok"].error == "tiktok account not authorized"
    assert result.upload.video_id == "yt123"


def test_force_private_overrides_privacy_override(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.youtube_api_key = None  # forces the legacy get_youtube_client() OAuth path, which is what's mocked below
    uploader_instance = MagicMock()
    uploader_instance.upload.return_value = UploadResult(
        video_id="yt123", url="https://youtube.com/shorts/yt123", privacy_status="private"
    )

    with _patch_stages(tmp_path), patch.multiple(
        "content_engine.pipeline",
        get_youtube_client=MagicMock(return_value=MagicMock()),
        YouTubeUploader=MagicMock(return_value=uploader_instance),
    ):
        run_pipeline(
            "stoic philosophy",
            settings,
            dry_run=False,
            privacy_override="public",
            force_private=True,
            target_platforms=["youtube"],
        )

    called_privacy = uploader_instance.upload.call_args.args[2]
    assert called_privacy == "private"
