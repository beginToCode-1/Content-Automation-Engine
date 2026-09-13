import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(pg_pool, tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    from content_engine.db import connection
    from content_engine.webapp.app import create_app

    # create_app()'s lifespan closes the shared connection pool on shutdown -
    # correct for a real, single-process deployment, but TestClient's __exit__
    # fires that shutdown after every individual test, which would kill the
    # pool the whole pytest session (via the pg_pool fixture) depends on.
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


def test_first_registered_user_becomes_admin(client):
    body = _register(client, "first@example.com")
    assert body["user"]["role"] == "admin"


def test_second_registered_user_becomes_viewer(client):
    _register(client, "first@example.com")
    body = _register(client, "second@example.com")
    assert body["user"]["role"] == "viewer"


def test_register_rejects_invalid_email(client):
    res = client.post("/api/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert res.status_code == 400


def test_register_rejects_short_password(client):
    res = client.post("/api/auth/register", json={"email": "a@example.com", "password": "short"})
    assert res.status_code == 400


def test_register_duplicate_email_returns_409(client):
    _register(client, "dup@example.com")
    res = client.post("/api/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert res.status_code == 409


def test_login_with_correct_credentials(client):
    _register(client, "user@example.com", "password123")
    res = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_returns_401(client):
    _register(client, "user@example.com", "password123")
    res = client.post("/api/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert res.status_code == 401


def test_login_with_unknown_email_returns_401(client):
    res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert res.status_code == 401


def test_me_requires_a_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user(client):
    body = _register(client, "user@example.com")
    res = client.get("/api/auth/me", headers=_auth_headers(body["access_token"]))
    assert res.status_code == 200
    assert res.json()["email"] == "user@example.com"


def test_viewer_cannot_create_a_run(client):
    _register(client, "admin@example.com")  # first user, becomes admin
    viewer = _register(client, "viewer@example.com")  # second user, becomes viewer

    res = client.post(
        "/api/runs",
        json={"topic": "stoicism", "mode": "generate_only", "platforms": ["youtube"]},
        headers=_auth_headers(viewer["access_token"]),
    )
    assert res.status_code == 403


def test_create_run_requires_auth(client):
    res = client.post("/api/runs", json={"topic": "stoicism"})
    assert res.status_code == 401


def test_users_only_see_their_own_runs(client, monkeypatch):
    admin = _register(client, "admin@example.com")
    other = _register(client, "other@example.com")

    # Insert a run directly for "other" without going through the (heavy)
    # pipeline - this test only cares about visibility, not generation.
    from content_engine.db import connection, runs_repo

    runs_repo.insert_run(connection.get_pool(), "other-run", "topic", "web", ["youtube"], user_id=other["user"]["id"])

    res = client.get("/api/runs", headers=_auth_headers(admin["access_token"]))
    assert res.status_code == 200
    assert res.json()["runs"] == []

    res_other = client.get("/api/runs", headers=_auth_headers(other["access_token"]))
    assert [r["run_id"] for r in res_other.json()["runs"]] == ["other-run"]


def test_get_run_not_owned_returns_404_not_403(client):
    admin = _register(client, "admin@example.com")
    other = _register(client, "other@example.com")

    from content_engine.db import connection, runs_repo

    runs_repo.insert_run(connection.get_pool(), "other-run", "topic", "web", ["youtube"], user_id=other["user"]["id"])

    res = client.get("/api/runs/other-run", headers=_auth_headers(admin["access_token"]))
    assert res.status_code == 404
