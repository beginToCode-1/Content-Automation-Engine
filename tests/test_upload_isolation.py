from unittest.mock import MagicMock, patch

import pytest

from content_engine import pipeline
from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata, UploadResult
from content_engine.uploaders.youtube_uploader import YouTubeUploader
from tests.test_pipeline_progress_callback import _fake_settings


def test_unexpected_error_on_one_platform_does_not_stop_the_others(tmp_path):
    broken = MagicMock()
    broken.upload.side_effect = ConnectionResetError("reset by peer")
    working = MagicMock()
    working.upload.return_value = UploadResult(video_id="t1", url="", privacy_status="SELF_ONLY")

    with patch.object(pipeline, "_build_uploader", side_effect=lambda p, c, s: broken if p == "instagram" else working):
        outcomes = pipeline.upload_clip_to_platforms(
            tmp_path / "clip.mp4", ClipMetadata(title="t", description="d"), ["instagram", "tiktok"],
            _fake_settings(tmp_path), "public", "topic", "run1",
        )

    assert [o.platform for o in outcomes] == ["instagram", "tiktok"]
    assert outcomes[0].result is None and "reset by peer" in outcomes[0].error
    assert outcomes[1].result.video_id == "t1"


def test_youtube_token_error_fails_only_youtube(tmp_path):
    working = MagicMock()
    working.upload.return_value = UploadResult(video_id="t1", url="", privacy_status="SELF_ONLY")
    with patch.object(pipeline, "_resolve_youtube_oauth_client", side_effect=RuntimeError("token revoked")), patch.object(
        pipeline, "_build_uploader", return_value=working
    ):
        outcomes = pipeline.upload_clip_to_platforms(
            tmp_path / "clip.mp4", ClipMetadata(title="t", description="d"), ["youtube", "tiktok"],
            _fake_settings(tmp_path), "private", "topic", "run1", youtube_account_id="acc1",
        )
    assert outcomes[0].result is None and "token revoked" in outcomes[0].error
    assert outcomes[1].result is not None


def test_youtube_network_error_mid_upload_is_retryable(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    client = MagicMock()
    client.videos.return_value.insert.return_value.next_chunk.side_effect = ConnectionResetError("reset")
    with pytest.raises(UploadFailedError) as exc:
        YouTubeUploader(client).upload(clip, ClipMetadata(title="t", description="d"), "private")
    assert exc.value.retryable is True
