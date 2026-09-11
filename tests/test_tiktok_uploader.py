from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from content_engine.auth import tiktok_oauth
from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata
from content_engine.uploaders.tiktok_uploader import TikTokUploader
from tests.test_pipeline_progress_callback import _fake_settings


def _configured_settings(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.tiktok_client_key = "client_key"
    settings.tiktok_client_secret = "client_secret"
    tiktok_oauth.save_token(
        settings.tiktok_token_path, {"access_token": "tok_abc", "refresh_token": "ref_abc", "expires_in": 86400}
    )
    return settings


def _fake_video_path(tmp_path) -> Path:
    run_dir = tmp_path / "work" / "runxyz789"
    run_dir.mkdir(parents=True, exist_ok=True)
    clip = run_dir / "clip_captioned.mp4"
    clip.write_bytes(b"fake video bytes")
    return clip


def _json_response(status_code, payload):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = str(payload)
    return response


def test_upload_not_configured_raises_upload_failed_error(tmp_path):
    settings = _fake_settings(tmp_path)
    uploader = TikTokUploader(settings)

    with pytest.raises(UploadFailedError, match="not configured"):
        uploader.upload(_fake_video_path(tmp_path), ClipMetadata(title="t", description="d"), "private")


def test_upload_picks_most_restrictive_available_privacy_level(tmp_path):
    settings = _configured_settings(tmp_path)
    uploader = TikTokUploader(settings)
    video_path = _fake_video_path(tmp_path)

    creator_info = _json_response(
        200, {"error": {"code": "ok"}, "data": {"privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]}}
    )
    init_response = _json_response(
        200, {"error": {"code": "ok"}, "data": {"publish_id": "pub123", "upload_url": "https://upload.example/x"}}
    )
    put_response = MagicMock(status_code=201)
    status_response = _json_response(200, {"data": {"status": "PUBLISH_COMPLETE"}})

    with patch("requests.post", side_effect=[creator_info, init_response, status_response]) as mock_post, patch(
        "requests.put", return_value=put_response
    ) as mock_put:
        result = uploader.upload(video_path, ClipMetadata(title="My Short #Shorts", description="d"), "private")

    assert result.video_id == "pub123"
    assert result.url == ""
    assert result.privacy_status == "SELF_ONLY"

    init_call = mock_post.call_args_list[1]
    assert init_call.kwargs["json"]["post_info"]["privacy_level"] == "SELF_ONLY"
    assert init_call.kwargs["json"]["source_info"]["video_size"] == len(b"fake video bytes")

    put_call = mock_put.call_args
    assert put_call.kwargs["headers"]["Content-Range"] == f"bytes 0-{len(b'fake video bytes') - 1}/{len(b'fake video bytes')}"


def test_upload_raises_when_publish_status_fails(tmp_path):
    settings = _configured_settings(tmp_path)
    uploader = TikTokUploader(settings)
    video_path = _fake_video_path(tmp_path)

    creator_info = _json_response(200, {"error": {"code": "ok"}, "data": {"privacy_level_options": ["SELF_ONLY"]}})
    init_response = _json_response(
        200, {"error": {"code": "ok"}, "data": {"publish_id": "pub123", "upload_url": "https://upload.example/x"}}
    )
    status_response = _json_response(200, {"data": {"status": "FAILED"}})

    with patch("requests.post", side_effect=[creator_info, init_response, status_response]), patch(
        "requests.put", return_value=MagicMock(status_code=201)
    ):
        with pytest.raises(UploadFailedError, match="publish failed"):
            uploader.upload(video_path, ClipMetadata(title="t", description="d"), "private")


def test_upload_rejects_video_larger_than_single_chunk_limit(tmp_path):
    settings = _configured_settings(tmp_path)
    uploader = TikTokUploader(settings)
    video_path = _fake_video_path(tmp_path)

    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 51 * 1024 * 1024
        with patch(
            "requests.post",
            return_value=_json_response(200, {"error": {"code": "ok"}, "data": {"privacy_level_options": ["SELF_ONLY"]}}),
        ):
            with pytest.raises(UploadFailedError, match="single-chunk"):
                uploader.upload(video_path, ClipMetadata(title="t", description="d"), "private")
