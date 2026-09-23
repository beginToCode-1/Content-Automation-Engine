from unittest.mock import MagicMock, patch

from content_engine import tunnel


def _reset_tunnel_state():
    tunnel._public_url = None


def test_should_start_tunnel_false_without_authtoken(monkeypatch):
    monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert tunnel.should_start_tunnel() is False


def test_should_start_tunnel_false_when_port_env_set(monkeypatch):
    monkeypatch.setenv("NGROK_AUTHTOKEN", "fake-token")
    monkeypatch.setenv("PORT", "10000")
    assert tunnel.should_start_tunnel() is False


def test_should_start_tunnel_true_when_authtoken_set_and_no_port(monkeypatch):
    monkeypatch.setenv("NGROK_AUTHTOKEN", "fake-token")
    monkeypatch.delenv("PORT", raising=False)
    assert tunnel.should_start_tunnel() is True


def test_start_tunnel_returns_none_when_not_opted_in(monkeypatch):
    monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
    _reset_tunnel_state()
    try:
        assert tunnel.start_tunnel(8000) is None
        assert tunnel.get_public_url() is None
    finally:
        _reset_tunnel_state()


def test_start_tunnel_sets_and_returns_https_url(monkeypatch):
    monkeypatch.setenv("NGROK_AUTHTOKEN", "fake-token")
    monkeypatch.delenv("PORT", raising=False)
    _reset_tunnel_state()

    fake_tunnel = MagicMock()
    fake_tunnel.public_url = "http://abcd1234.ngrok.io"

    try:
        with patch("pyngrok.ngrok.set_auth_token") as mock_set_token, patch(
            "pyngrok.ngrok.connect", return_value=fake_tunnel
        ) as mock_connect:
            url = tunnel.start_tunnel(8000)

        mock_set_token.assert_called_once_with("fake-token")
        mock_connect.assert_called_once_with(8000, "http")
        assert url == "https://abcd1234.ngrok.io"
        assert tunnel.get_public_url() == "https://abcd1234.ngrok.io"

        # A second call is a no-op that returns the already-active URL,
        # without starting a second tunnel.
        with patch("pyngrok.ngrok.connect") as mock_connect_again:
            second_url = tunnel.start_tunnel(8000)
        mock_connect_again.assert_not_called()
        assert second_url == url
    finally:
        _reset_tunnel_state()


def test_stop_tunnel_clears_state(monkeypatch):
    monkeypatch.setenv("NGROK_AUTHTOKEN", "fake-token")
    monkeypatch.delenv("PORT", raising=False)
    _reset_tunnel_state()

    fake_tunnel = MagicMock()
    fake_tunnel.public_url = "http://abcd1234.ngrok.io"

    try:
        with patch("pyngrok.ngrok.set_auth_token"), patch("pyngrok.ngrok.connect", return_value=fake_tunnel):
            tunnel.start_tunnel(8000)

        with patch("pyngrok.ngrok.kill") as mock_kill:
            tunnel.stop_tunnel()
        mock_kill.assert_called_once()
        assert tunnel.get_public_url() is None
    finally:
        _reset_tunnel_state()
