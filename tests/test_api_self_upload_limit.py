from tests.test_api_users import _auth_headers, _register, client  # noqa: F401  (fixture)


def test_oversized_upload_is_rejected_and_not_kept(client, monkeypatch, tmp_path):
    from content_engine.webapp.routes import api_self_upload

    monkeypatch.setattr(api_self_upload, "MAX_UPLOAD_BYTES", 1024)
    token = _register(client, "admin@example.com")["access_token"]
    res = client.post(
        "/api/self-upload/draft",
        headers=_auth_headers(token),
        files={"file": ("big.mp4", b"x" * 5000, "video/mp4")},
        data={"hint": "stoicism"},
    )
    assert res.status_code == 413
    work = tmp_path / "work"
    assert not any(p.is_dir() for p in work.iterdir())  # draft folder removed
