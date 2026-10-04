import pytest

from content_engine.config import _env_bool, _env_int
from content_engine.errors import ConfigError


@pytest.mark.parametrize("raw,expected", [("1", True), ("YES", True), ("true", True), ("0", False), ("off", False)])
def test_env_bool_accepts_common_spellings(monkeypatch, raw, expected):
    monkeypatch.setenv("X_FLAG", raw)
    assert _env_bool("X_FLAG", not expected) is expected


def test_env_bool_blank_uses_default_and_garbage_raises(monkeypatch):
    monkeypatch.setenv("X_FLAG", "")
    assert _env_bool("X_FLAG", True) is True
    monkeypatch.setenv("X_FLAG", "maybe")
    with pytest.raises(ConfigError):
        _env_bool("X_FLAG", True)


def test_env_int_blank_uses_default_and_garbage_raises(monkeypatch):
    monkeypatch.setenv("X_NUM", "")
    assert _env_int("X_NUM", 3) == 3
    monkeypatch.setenv("X_NUM", "abc")
    with pytest.raises(ConfigError, match="X_NUM"):
        _env_int("X_NUM", 3)


def test_instagram_video_url_falls_back_to_render_external_url(monkeypatch):
    from content_engine.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_SECRET_KEY", "k")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("INSTAGRAM_PUBLIC_VIDEO_BASE_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://app.onrender.com/")
    assert Settings.load().instagram_public_video_base_url == "https://app.onrender.com"

    monkeypatch.setenv("INSTAGRAM_PUBLIC_VIDEO_BASE_URL", "https://explicit.example")
    assert Settings.load().instagram_public_video_base_url == "https://explicit.example"
