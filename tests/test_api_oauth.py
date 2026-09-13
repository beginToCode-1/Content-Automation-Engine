from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(pg_pool, tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "vG5mbRH65nHC_fwqRmsPa_jM5p2bvPT3LPCPvR7Rj4Y=")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://testserver/api/oauth/youtube/callback")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://frontend.example.com")

    from content_engine.db import connection
    from content_engine.webapp.app import create_app

    # See test_api_auth.py's client fixture for why this is needed - without
    # it, TestClient's shutdown-on-exit closes the pool the rest of the test
    # session's pg_pool fixture depends on.
    monkeypatch.setattr(connection, "close_pool", lambda: None)

    app = create_app()
    with TestClient(app, follow_redirects=False) as c:
        yield c


def _register(client, email="user@example.com", password="password123"):
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _get_ticket(client, access_token):
    res = client.post("/api/oauth/youtube/connect-ticket", headers=_auth_headers(access_token))
    assert res.status_code == 200, res.text
    return res.json()["ticket"]


def test_connect_ticket_requires_auth(client):
    res = client.post("/api/oauth/youtube/connect-ticket")
    assert res.status_code == 401


def test_connect_requires_a_valid_ticket(client):
    res = client.get("/api/oauth/youtube/connect", params={"ticket": "not-a-real-ticket"})
    assert res.status_code == 401


def test_connect_redirects_to_google(client):
    user = _register(client)
    ticket = _get_ticket(client, user["access_token"])
    res = client.get("/api/oauth/youtube/connect", params={"ticket": ticket})
    assert res.status_code == 302
    assert "accounts.google.com" in res.headers["location"]


def test_callback_with_provider_error_redirects_to_frontend_with_error(client):
    res = client.get("/api/oauth/youtube/callback", params={"error": "access_denied"})
    assert res.status_code == 302
    assert res.headers["location"] == "http://frontend.example.com/accounts?error=access_denied"


def test_callback_with_invalid_state_redirects_with_error(client):
    res = client.get("/api/oauth/youtube/callback", params={"code": "abc", "state": "garbage"})
    assert res.status_code == 302
    assert "error=invalid_state" in res.headers["location"]


def test_callback_success_stores_connected_account(client):
    user = _register(client)

    ticket = _get_ticket(client, user["access_token"])
    connect_res = client.get("/api/oauth/youtube/connect", params={"ticket": ticket})
    state = connect_res.headers["location"].split("state=")[1].split("&")[0]

    fake_creds = MagicMock(token="access-tok", refresh_token="refresh-tok", scopes=["scope-a"], expiry=None)

    with patch(
        "content_engine.webapp.routes.api_oauth.google_oauth.exchange_code_for_credentials",
        return_value=fake_creds,
    ), patch(
        "content_engine.webapp.routes.api_oauth.google_oauth.fetch_channel_info",
        return_value=("UC123", "My Test Channel"),
    ):
        res = client.get("/api/oauth/youtube/callback", params={"code": "auth-code", "state": state})

    assert res.status_code == 302
    assert res.headers["location"] == "http://frontend.example.com/accounts?connected=youtube"

    accounts_res = client.get("/api/accounts", headers=_auth_headers(user["access_token"]))
    accounts = accounts_res.json()["accounts"]
    assert len(accounts) == 1
    assert accounts[0]["account_label"] == "My Test Channel"
    assert accounts[0]["external_account_id"] == "UC123"
    assert "access_token" not in accounts[0]


def test_list_accounts_requires_auth(client):
    res = client.get("/api/accounts")
    assert res.status_code == 401


def test_disconnect_account_requires_ownership(client):
    user_a = _register(client, "a@example.com")
    user_b = _register(client, "b@example.com")

    ticket = _get_ticket(client, user_a["access_token"])
    connect_res = client.get("/api/oauth/youtube/connect", params={"ticket": ticket})
    state = connect_res.headers["location"].split("state=")[1].split("&")[0]
    fake_creds = MagicMock(token="t", refresh_token="r", scopes=[], expiry=None)
    with patch(
        "content_engine.webapp.routes.api_oauth.google_oauth.exchange_code_for_credentials",
        return_value=fake_creds,
    ), patch(
        "content_engine.webapp.routes.api_oauth.google_oauth.fetch_channel_info",
        return_value=("UC1", "A's Channel"),
    ):
        client.get("/api/oauth/youtube/callback", params={"code": "c", "state": state})

    account_id = client.get("/api/accounts", headers=_auth_headers(user_a["access_token"])).json()["accounts"][0]["id"]

    res_wrong_user = client.delete(f"/api/accounts/{account_id}", headers=_auth_headers(user_b["access_token"]))
    assert res_wrong_user.status_code == 404

    res_owner = client.delete(f"/api/accounts/{account_id}", headers=_auth_headers(user_a["access_token"]))
    assert res_owner.status_code == 200
