import sqlite3

import pytest

from content_engine.db.connection import init_db
from content_engine.db import users_repo


def _fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_create_and_get_user_by_email(tmp_path):
    db_path = _fresh_db(tmp_path)
    created = users_repo.create_user(db_path, "admin@example.com", "hashed", "admin")

    row = users_repo.get_user_by_email(db_path, "admin@example.com")
    assert row["id"] == created["id"]
    assert row["role"] == "admin"
    assert row["password_hash"] == "hashed"


def test_get_user_by_email_is_case_insensitive(tmp_path):
    db_path = _fresh_db(tmp_path)
    users_repo.create_user(db_path, "Admin@Example.com", "hashed", "admin")

    assert users_repo.get_user_by_email(db_path, "admin@example.com") is not None


def test_get_user_by_email_missing_returns_none(tmp_path):
    db_path = _fresh_db(tmp_path)
    assert users_repo.get_user_by_email(db_path, "nobody@example.com") is None


def test_get_user_by_id(tmp_path):
    db_path = _fresh_db(tmp_path)
    created = users_repo.create_user(db_path, "viewer@example.com", "hashed", "viewer")

    row = users_repo.get_user_by_id(db_path, created["id"])
    assert row["email"] == "viewer@example.com"


def test_duplicate_email_raises_integrity_error(tmp_path):
    db_path = _fresh_db(tmp_path)
    users_repo.create_user(db_path, "dup@example.com", "hashed", "viewer")

    with pytest.raises(sqlite3.IntegrityError):
        users_repo.create_user(db_path, "dup@example.com", "hashed2", "viewer")


def test_count_users(tmp_path):
    db_path = _fresh_db(tmp_path)
    assert users_repo.count_users(db_path) == 0

    users_repo.create_user(db_path, "a@example.com", "hashed", "admin")
    assert users_repo.count_users(db_path) == 1

    users_repo.create_user(db_path, "b@example.com", "hashed", "viewer")
    assert users_repo.count_users(db_path) == 2
