from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from content_engine.config import Settings
from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata
from content_engine.uploaders.instagram_uploader import InstagramUploader
from tests.test_pipeline_progress_callback import _fake_settings


def _configured_settings(tmp_path) -> Settings:
    settings = _fake_settings(tmp_path)
    settings.instagram_access_token = "token123"
    settings.instagram_business_account_id = "ig_user_1"
    settings.instagram_public_video_base_url = "https://example.ngrok.io"
    return settings


def _fake_video_path(tmp_path) -> Path:
    run_dir = tmp_path / "work" / "runabc123"
    run_dir.mkdir(parents=True, exist_ok=True)
    clip = run_dir / "clip_captioned.mp4"
    clip.write_bytes(b"fake")
    return clip


def _json_response(status_code, payload):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_upload_missing_config_raises_upload_failed_error(tmp_path):
    settings = _fake_settings(tmp_path)  # instagram_* fields left None
    uploader = InstagramUploader(settings)

    with pytest.raises(UploadFailedError, match="not configured"):
        uploader.upload(_fake_video_path(tmp_path), ClipMetadata(title="t", description="d"), "private")


def test_upload_missing_public_base_url_raises_upload_failed_error(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.instagram_access_token = "token123"
    settings.instagram_business_account_id = "ig_user_1"
    uploader = InstagramUploader(settings)

    with pytest.raises(UploadFailedError, match="PUBLIC_VIDEO_BASE_URL"):
        uploader.upload(_fake_video_path(tmp_path), ClipMetadata(title="t", description="d"), "private")


def test_upload_happy_path_builds_correct_video_url_and_returns_permalink(tmp_path):
    settings = _configured_settings(tmp_path)
    uploader = InstagramUploader(settings)
    video_path = _fake_video_path(tmp_path)

    responses = [
        _json_response(200, {"id": "container123"}),
        _json_response(200, {"status_code": "FINISHED"}),
        _json_response(200, {"id": "media789"}),
        _json_response(200, {"permalink": "https://instagram.com/reel/media789/"}),
    ]

    with patch("requests.post", side_effect=[responses[0], responses[2]]) as mock_post, patch(
        "requests.get", side_effect=[responses[1], responses[3]]
    ) as mock_get:
        result = uploader.upload(video_path, ClipMetadata(title="t", description="d", hashtags=["x"]), "private")

    assert result.video_id == "media789"
    assert result.url == "https://instagram.com/reel/media789/"

    create_call = mock_post.call_args_list[0]
    assert create_call.kwargs["data"]["video_url"] == "https://example.ngrok.io/media/runabc123/clip.mp4"
    assert create_call.kwargs["data"]["media_type"] == "REELS"

    publish_call = mock_post.call_args_list[1]
    assert publish_call.kwargs["data"]["creation_id"] == "container123"


def test_upload_raises_when_container_errors(tmp_path):
    settings = _configured_settings(tmp_path)
    uploader = InstagramUploader(settings)
    video_path = _fake_video_path(tmp_path)

    with patch("requests.post", return_value=_json_response(200, {"id": "container123"})), patch(
        "requests.get", return_value=_json_response(200, {"status_code": "ERROR"})
    ):
        with pytest.raises(UploadFailedError, match="failed to process"):
            uploader.upload(video_path, ClipMetadata(title="t", description="d"), "private")
