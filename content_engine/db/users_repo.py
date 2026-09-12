import sqlite3
import uuid
from pathlib import Path

from content_engine.db.connection import get_connection


def count_users(db_path: Path) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return row["n"]
    finally:
        conn.close()


def create_user(db_path: Path, email: str, password_hash: str, role: str) -> dict:
    """Raises sqlite3.IntegrityError if the email is already registered
    (UNIQUE COLLATE NOCASE constraint) - callers translate that into a 409."""
    user_id = uuid.uuid4().hex
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, role),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": user_id, "email": email, "role": role}


def create_user_with_bootstrap_role(db_path: Path, email: str, password_hash: str) -> dict:
    """Same "first account ever becomes admin, everyone after that is viewer"
    rule the register route used to compute via a separate count_users() call
    followed by create_user() - but atomically, via BEGIN IMMEDIATE, so two
    concurrent registrations hitting a fresh deployment at once can't both
    observe zero users and both become admin (the second blocks on the write
    lock until the first commits, then correctly sees count=1)."""
    user_id = uuid.uuid4().hex
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        role = "admin" if count == 0 else "viewer"
        conn.execute(
            "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, role),
        )
        conn.commit()
        return {"id": user_id, "email": email, "role": role}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_email(db_path: Path, email: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(db_path: Path, user_id: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
