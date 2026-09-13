from cryptography.fernet import Fernet

from content_engine.db import connected_accounts_repo, users_repo


def _key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _make_user(pool) -> str:
    return users_repo.create_user(pool, "user@example.com", "hashed", "admin")["id"]


def test_upsert_creates_and_get_account_decrypts(pg_pool):
    key = _key()
    user_id = _make_user(pg_pool)

    account_id = connected_accounts_repo.upsert_account(
        pg_pool,
        key,
        user_id=user_id,
        platform="youtube",
        account_label="My Channel",
        external_account_id="UC123",
        access_token="access-1",
        refresh_token="refresh-1",
        token_expiry="2026-01-01T00:00:00.000000Z",
        scopes=["a", "b"],
    )

    row = connected_accounts_repo.get_account(pg_pool, account_id, key)
    assert row["access_token"] == "access-1"
    assert row["refresh_token"] == "refresh-1"
    assert row["scopes"] == ["a", "b"]
    assert row["account_label"] == "My Channel"


def test_upsert_same_external_account_updates_in_place(pg_pool):
    key = _key()
    user_id = _make_user(pg_pool)

    first_id = connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_id, platform="youtube", account_label="Old Name",
        external_account_id="UC123", access_token="access-1", refresh_token="refresh-1",
        token_expiry=None, scopes=[],
    )
    second_id = connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_id, platform="youtube", account_label="New Name",
        external_account_id="UC123", access_token="access-2", refresh_token="refresh-2",
        token_expiry=None, scopes=[],
    )

    assert first_id == second_id
    accounts = connected_accounts_repo.list_accounts_public(pg_pool, user_id)
    assert len(accounts) == 1
    assert accounts[0]["account_label"] == "New Name"


def test_upsert_keeps_existing_refresh_token_when_none_given(pg_pool):
    key = _key()
    user_id = _make_user(pg_pool)

    account_id = connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_id, platform="youtube", account_label="Ch",
        external_account_id="UC123", access_token="access-1", refresh_token="refresh-1",
        token_expiry=None, scopes=[],
    )
    connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_id, platform="youtube", account_label="Ch",
        external_account_id="UC123", access_token="access-2", refresh_token=None,
        token_expiry=None, scopes=[],
    )

    row = connected_accounts_repo.get_account(pg_pool, account_id, key)
    assert row["access_token"] == "access-2"
    assert row["refresh_token"] == "refresh-1"


def test_list_accounts_public_excludes_tokens(pg_pool):
    key = _key()
    user_id = _make_user(pg_pool)
    connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_id, platform="youtube", account_label="Ch",
        external_account_id="UC123", access_token="access-1", refresh_token="refresh-1",
        token_expiry=None, scopes=[],
    )

    accounts = connected_accounts_repo.list_accounts_public(pg_pool, user_id)
    assert "access_token" not in accounts[0]
    assert "refresh_token" not in accounts[0]


def test_list_accounts_public_scoped_to_user(pg_pool):
    key = _key()
    user_a = _make_user(pg_pool)
    user_b = users_repo.create_user(pg_pool, "b@example.com", "hashed", "viewer")["id"]

    connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_a, platform="youtube", account_label="A's channel",
        external_account_id="UC-A", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
    )

    assert len(connected_accounts_repo.list_accounts_public(pg_pool, user_a)) == 1
    assert len(connected_accounts_repo.list_accounts_public(pg_pool, user_b)) == 0


def test_delete_account_requires_matching_owner(pg_pool):
    key = _key()
    user_a = _make_user(pg_pool)
    user_b = users_repo.create_user(pg_pool, "b@example.com", "hashed", "viewer")["id"]

    account_id = connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_a, platform="youtube", account_label="A's channel",
        external_account_id="UC-A", access_token="a", refresh_token="a", token_expiry=None, scopes=[],
    )

    assert connected_accounts_repo.delete_account(pg_pool, account_id, user_b) is False
    assert connected_accounts_repo.delete_account(pg_pool, account_id, user_a) is True
    assert connected_accounts_repo.list_accounts_public(pg_pool, user_a) == []


def test_update_tokens_overwrites_access_token_only_by_default(pg_pool):
    key = _key()
    user_id = _make_user(pg_pool)
    account_id = connected_accounts_repo.upsert_account(
        pg_pool, key, user_id=user_id, platform="youtube", account_label="Ch",
        external_account_id="UC123", access_token="access-1", refresh_token="refresh-1",
        token_expiry=None, scopes=[],
    )

    connected_accounts_repo.update_tokens(pg_pool, key, account_id, access_token="access-2", token_expiry=None)

    row = connected_accounts_repo.get_account(pg_pool, account_id, key)
    assert row["access_token"] == "access-2"
    assert row["refresh_token"] == "refresh-1"
