from unittest.mock import MagicMock, patch

import pytest

from content_engine.errors import UploadFailedError
from content_engine.models import UploadResult
from content_engine.pipeline import run_pipeline
from tests.test_pipeline_progress_callback import _fake_settings, _patch_stages


def test_retryable_upload_failure_succeeds_after_retries(tmp_path):
    settings = _fake_settings(tmp_path)
    fake_uploader = MagicMock()
    fake_uploader.upload.side_effect = [
        UploadFailedError("transient blip", retryable=True),
        UploadFailedError("transient blip", retryable=True),
        UploadResult(video_id="vid123", url="", privacy_status="SELF_ONLY"),
    ]

    # "tiktok" (not "youtube") - youtube uploads need an oauth_client resolved
    # up front and fail before _build_uploader is ever reached if there isn't
    # one, which isn't what this test is about.
    with _patch_stages(tmp_path), \
        patch("content_engine.pipeline._build_uploader", return_value=fake_uploader), \
        patch("content_engine.pipeline.time.sleep"):
        result = run_pipeline("stoic philosophy", settings, dry_run=False, target_platforms=["tiktok"])

    assert fake_uploader.upload.call_count == 3
    assert result.uploads[0].result is not None
    assert result.uploads[0].result.video_id == "vid123"


def test_non_retryable_upload_failure_does_not_retry(tmp_path):
    settings = _fake_settings(tmp_path)
    fake_uploader = MagicMock()
    fake_uploader.upload.side_effect = UploadFailedError("bad credentials", retryable=False)

    with _patch_stages(tmp_path), \
        patch("content_engine.pipeline._build_uploader", return_value=fake_uploader), \
        patch("content_engine.pipeline.time.sleep") as mock_sleep:
        with pytest.raises(UploadFailedError):
            run_pipeline("stoic philosophy", settings, dry_run=False, target_platforms=["tiktok"])

    assert fake_uploader.upload.call_count == 1
    mock_sleep.assert_not_called()


def test_retryable_upload_failure_gives_up_after_max_retries(tmp_path):
    settings = _fake_settings(tmp_path)
    fake_uploader = MagicMock()
    fake_uploader.upload.side_effect = UploadFailedError("still failing", retryable=True)

    with _patch_stages(tmp_path), \
        patch("content_engine.pipeline._build_uploader", return_value=fake_uploader), \
        patch("content_engine.pipeline.time.sleep"):
        with pytest.raises(UploadFailedError):
            run_pipeline("stoic philosophy", settings, dry_run=False, target_platforms=["tiktok"])

    # settings.upload_max_retries=3 -> 1 initial attempt + 3 retries = 4 calls
    assert fake_uploader.upload.call_count == settings.upload_max_retries + 1
