import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(pg_pool, tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    from content_engine.db import connection
    from content_engine.webapp.app import create_app

    monkeypatch.setattr(connection, "close_pool", lambda: None)

    app = create_app()
    with TestClient(app) as c:
        yield c


def _register(client, email, password="password123"):
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_list_users(client):
    admin = _register(client, "admin@example.com")  # first user, becomes admin
    _register(client, "viewer@example.com")  # second user, becomes viewer

    res = client.get("/api/users", headers=_auth_headers(admin["access_token"]))
    assert res.status_code == 200
    emails = {u["email"] for u in res.json()}
    assert emails == {"admin@example.com", "viewer@example.com"}


def test_viewer_cannot_list_users(client):
    _register(client, "admin@example.com")
    viewer = _register(client, "viewer@example.com")

    res = client.get("/api/users", headers=_auth_headers(viewer["access_token"]))
    assert res.status_code == 403


def test_list_users_requires_auth(client):
    res = client.get("/api/users")
    assert res.status_code == 401


def test_admin_can_promote_a_viewer(client):
    admin = _register(client, "admin@example.com")
    viewer = _register(client, "viewer@example.com")

    res = client.put(
        f"/api/users/{viewer['user']['id']}/role",
        json={"role": "admin"},
        headers=_auth_headers(admin["access_token"]),
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_admin_cannot_demote_own_account(client):
    admin = _register(client, "admin@example.com")

    res = client.put(
        f"/api/users/{admin['user']['id']}/role",
        json={"role": "viewer"},
        headers=_auth_headers(admin["access_token"]),
    )
    assert res.status_code == 400


def test_update_role_rejects_invalid_role(client):
    admin = _register(client, "admin@example.com")
    viewer = _register(client, "viewer@example.com")

    res = client.put(
        f"/api/users/{viewer['user']['id']}/role",
        json={"role": "superadmin"},
        headers=_auth_headers(admin["access_token"]),
    )
    assert res.status_code == 400


def test_update_role_unknown_user_returns_404(client):
    admin = _register(client, "admin@example.com")

    res = client.put(
        "/api/users/no-such-id/role",
        json={"role": "admin"},
        headers=_auth_headers(admin["access_token"]),
    )
    assert res.status_code == 404


def test_viewer_cannot_update_role(client):
    _register(client, "admin@example.com")
    viewer = _register(client, "viewer@example.com")

    res = client.put(
        f"/api/users/{viewer['user']['id']}/role",
        json={"role": "admin"},
        headers=_auth_headers(viewer["access_token"]),
    )
    assert res.status_code == 403
