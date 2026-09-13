from cryptography.fernet import Fernet
import pytest
from fastapi import HTTPException

from content_engine.db import connected_accounts_repo, users_repo
from content_engine.webapp.account_selection import resolve_youtube_account_id


def _key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _make_user(pool) -> dict:
    return users_repo.create_user(pool, "user@example.com", "hashed", "admin")


def test_returns_none_when_youtube_not_requested(pg_pool):
    user = _make_user(pg_pool)

    assert resolve_youtube_account_id(pg_pool, user, ["instagram"], None) is None


def test_auto_selects_the_only_connected_account(pg_pool):
    user = _make_user(pg_pool)
    account_id = connected_accounts_repo.upsert_account(
        pg_pool, _key(), user_id=user["id"], platform="youtube", account_label="Ch",
        external_account_id="UC1", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
    )

    resolved = resolve_youtube_account_id(pg_pool, user, ["youtube"], None)
    assert resolved == account_id


def test_no_connected_accounts_raises_400(pg_pool):
    user = _make_user(pg_pool)

    with pytest.raises(HTTPException) as exc_info:
        resolve_youtube_account_id(pg_pool, user, ["youtube"], None)
    assert exc_info.value.status_code == 400


def test_multiple_accounts_without_explicit_choice_raises_400(pg_pool):
    user = _make_user(pg_pool)
    for i in range(2):
        connected_accounts_repo.upsert_account(
            pg_pool, _key(), user_id=user["id"], platform="youtube", account_label=f"Ch{i}",
            external_account_id=f"UC{i}", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
        )

    with pytest.raises(HTTPException) as exc_info:
        resolve_youtube_account_id(pg_pool, user, ["youtube"], None)
    assert exc_info.value.status_code == 400


def test_explicit_valid_account_id_is_returned(pg_pool):
    user = _make_user(pg_pool)
    ids = [
        connected_accounts_repo.upsert_account(
            pg_pool, _key(), user_id=user["id"], platform="youtube", account_label=f"Ch{i}",
            external_account_id=f"UC{i}", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
        )
        for i in range(2)
    ]

    resolved = resolve_youtube_account_id(pg_pool, user, ["youtube"], ids[1])
    assert resolved == ids[1]


def test_explicit_account_id_not_owned_by_user_raises_400(pg_pool):
    user_a = _make_user(pg_pool)
    user_b = users_repo.create_user(pg_pool, "b@example.com", "hashed", "viewer")
    other_account_id = connected_accounts_repo.upsert_account(
        pg_pool, _key(), user_id=user_b["id"], platform="youtube", account_label="B's channel",
        external_account_id="UC-B", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        resolve_youtube_account_id(pg_pool, user_a, ["youtube"], other_account_id)
    assert exc_info.value.status_code == 400
