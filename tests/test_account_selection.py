from cryptography.fernet import Fernet
import pytest
from fastapi import HTTPException

from content_engine.db.connection import init_db
from content_engine.db import connected_accounts_repo, users_repo
from content_engine.webapp.account_selection import resolve_youtube_account_id


class _FakeSettings:
    def __init__(self, db_path):
        self.db_path = db_path


def _fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _make_user(db_path) -> dict:
    return users_repo.create_user(db_path, "user@example.com", "hashed", "admin")


def test_returns_none_when_youtube_not_requested(tmp_path):
    db_path = _fresh_db(tmp_path)
    user = _make_user(db_path)
    settings = _FakeSettings(db_path)

    assert resolve_youtube_account_id(settings, user, ["instagram"], None) is None


def test_auto_selects_the_only_connected_account(tmp_path):
    db_path = _fresh_db(tmp_path)
    user = _make_user(db_path)
    settings = _FakeSettings(db_path)
    account_id = connected_accounts_repo.upsert_account(
        db_path, _key(), user_id=user["id"], platform="youtube", account_label="Ch",
        external_account_id="UC1", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
    )

    resolved = resolve_youtube_account_id(settings, user, ["youtube"], None)
    assert resolved == account_id


def test_no_connected_accounts_raises_400(tmp_path):
    db_path = _fresh_db(tmp_path)
    user = _make_user(db_path)
    settings = _FakeSettings(db_path)

    with pytest.raises(HTTPException) as exc_info:
        resolve_youtube_account_id(settings, user, ["youtube"], None)
    assert exc_info.value.status_code == 400


def test_multiple_accounts_without_explicit_choice_raises_400(tmp_path):
    db_path = _fresh_db(tmp_path)
    user = _make_user(db_path)
    settings = _FakeSettings(db_path)
    for i in range(2):
        connected_accounts_repo.upsert_account(
            db_path, _key(), user_id=user["id"], platform="youtube", account_label=f"Ch{i}",
            external_account_id=f"UC{i}", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
        )

    with pytest.raises(HTTPException) as exc_info:
        resolve_youtube_account_id(settings, user, ["youtube"], None)
    assert exc_info.value.status_code == 400


def test_explicit_valid_account_id_is_returned(tmp_path):
    db_path = _fresh_db(tmp_path)
    user = _make_user(db_path)
    settings = _FakeSettings(db_path)
    ids = [
        connected_accounts_repo.upsert_account(
            db_path, _key(), user_id=user["id"], platform="youtube", account_label=f"Ch{i}",
            external_account_id=f"UC{i}", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
        )
        for i in range(2)
    ]

    resolved = resolve_youtube_account_id(settings, user, ["youtube"], ids[1])
    assert resolved == ids[1]


def test_explicit_account_id_not_owned_by_user_raises_400(tmp_path):
    db_path = _fresh_db(tmp_path)
    user_a = _make_user(db_path)
    user_b = users_repo.create_user(db_path, "b@example.com", "hashed", "viewer")
    settings = _FakeSettings(db_path)
    other_account_id = connected_accounts_repo.upsert_account(
        db_path, _key(), user_id=user_b["id"], platform="youtube", account_label="B's channel",
        external_account_id="UC-B", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        resolve_youtube_account_id(settings, user_a, ["youtube"], other_account_id)
    assert exc_info.value.status_code == 400
