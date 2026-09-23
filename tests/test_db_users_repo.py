import pytest

from content_engine.db import users_repo


def test_create_and_get_user_by_email(pg_pool):
    created = users_repo.create_user(pg_pool, "admin@example.com", "hashed", "admin")

    row = users_repo.get_user_by_email(pg_pool, "admin@example.com")
    assert row["id"] == created["id"]
    assert row["role"] == "admin"
    assert row["password_hash"] == "hashed"


def test_get_user_by_email_is_case_insensitive(pg_pool):
    users_repo.create_user(pg_pool, "Admin@Example.com", "hashed", "admin")

    assert users_repo.get_user_by_email(pg_pool, "admin@example.com") is not None


def test_get_user_by_email_missing_returns_none(pg_pool):
    assert users_repo.get_user_by_email(pg_pool, "nobody@example.com") is None


def test_get_user_by_id(pg_pool):
    created = users_repo.create_user(pg_pool, "viewer@example.com", "hashed", "viewer")

    row = users_repo.get_user_by_id(pg_pool, created["id"])
    assert row["email"] == "viewer@example.com"


def test_duplicate_email_raises_duplicate_email_error(pg_pool):
    users_repo.create_user(pg_pool, "dup@example.com", "hashed", "viewer")

    with pytest.raises(users_repo.DuplicateEmailError):
        users_repo.create_user(pg_pool, "dup@example.com", "hashed2", "viewer")


def test_count_users(pg_pool):
    assert users_repo.count_users(pg_pool) == 0

    users_repo.create_user(pg_pool, "a@example.com", "hashed", "admin")
    assert users_repo.count_users(pg_pool) == 1

    users_repo.create_user(pg_pool, "b@example.com", "hashed", "viewer")
    assert users_repo.count_users(pg_pool) == 2


def test_bootstrap_role_first_user_is_admin(pg_pool):
    user = users_repo.create_user_with_bootstrap_role(pg_pool, "first@example.com", "hashed")
    assert user["role"] == "admin"


def test_bootstrap_role_second_user_is_viewer(pg_pool):
    users_repo.create_user_with_bootstrap_role(pg_pool, "first@example.com", "hashed")
    second = users_repo.create_user_with_bootstrap_role(pg_pool, "second@example.com", "hashed")
    assert second["role"] == "viewer"


def test_bootstrap_role_duplicate_email_raises(pg_pool):
    users_repo.create_user_with_bootstrap_role(pg_pool, "dup@example.com", "hashed")
    with pytest.raises(users_repo.DuplicateEmailError):
        users_repo.create_user_with_bootstrap_role(pg_pool, "dup@example.com", "hashed2")


def test_list_users_returns_all_users_ordered_by_created_at(pg_pool):
    first = users_repo.create_user(pg_pool, "a@example.com", "hashed", "admin")
    second = users_repo.create_user(pg_pool, "b@example.com", "hashed", "viewer")

    rows = users_repo.list_users(pg_pool)
    assert [r["id"] for r in rows] == [first["id"], second["id"]]


def test_update_role_changes_role_and_returns_row(pg_pool):
    created = users_repo.create_user(pg_pool, "viewer@example.com", "hashed", "viewer")

    updated = users_repo.update_role(pg_pool, created["id"], "admin")
    assert updated["role"] == "admin"
    assert users_repo.get_user_by_id(pg_pool, created["id"])["role"] == "admin"


def test_update_role_returns_none_for_unknown_user(pg_pool):
    assert users_repo.update_role(pg_pool, "no-such-id", "admin") is None
