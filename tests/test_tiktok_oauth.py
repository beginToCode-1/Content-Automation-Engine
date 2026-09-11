import time
from unittest.mock import MagicMock, patch

import pytest

from content_engine.auth import tiktok_oauth
from content_engine.errors import UploadFailedError
from tests.test_pipeline_progress_callback import _fake_settings


def _configured_settings(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.tiktok_client_key = "client_key"
    settings.tiktok_client_secret = "client_secret"
    return settings


def test_get_access_token_raises_when_not_configured(tmp_path):
    settings = _fake_settings(tmp_path)
    with pytest.raises(UploadFailedError, match="not configured"):
        tiktok_oauth.get_access_token(settings)


def test_get_access_token_raises_when_no_cached_token(tmp_path):
    settings = _configured_settings(tmp_path)
    with pytest.raises(UploadFailedError, match="tiktok-auth"):
        tiktok_oauth.get_access_token(settings)


def test_get_access_token_returns_cached_token_when_not_expired(tmp_path):
    settings = _configured_settings(tmp_path)
    tiktok_oauth.save_token(
        settings.tiktok_token_path, {"access_token": "fresh_token", "refresh_token": "r1", "expires_in": 86400}
    )

    with patch("requests.post") as mock_post:
        token = tiktok_oauth.get_access_token(settings)

    assert token == "fresh_token"
    mock_post.assert_not_called()


def test_get_access_token_refreshes_when_expired(tmp_path):
    settings = _configured_settings(tmp_path)
    token_data = {"access_token": "old_token", "refresh_token": "r1", "expires_in": 100}
    tiktok_oauth.save_token(settings.tiktok_token_path, token_data)
    stored = tiktok_oauth.load_token(settings.tiktok_token_path)
    stored["_saved_at"] = time.time() - 1000  # force expiry
    settings.tiktok_token_path.write_text(__import__("json").dumps(stored), encoding="utf-8")

    refreshed_response = MagicMock(status_code=200)
    refreshed_response.json.return_value = {"access_token": "new_token", "refresh_token": "r2", "expires_in": 86400}

    with patch("requests.post", return_value=refreshed_response) as mock_post:
        token = tiktok_oauth.get_access_token(settings)

    assert token == "new_token"
    mock_post.assert_called_once()
    assert tiktok_oauth.load_token(settings.tiktok_token_path)["access_token"] == "new_token"
