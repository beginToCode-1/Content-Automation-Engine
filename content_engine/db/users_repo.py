import uuid

import psycopg
from psycopg_pool import ConnectionPool

# Arbitrary fixed key for pg_advisory_xact_lock, guarding the "first user
# ever becomes admin" race in create_user_with_bootstrap_role below. Any
# constant works as long as it's used consistently - it just needs to
# serialize concurrent callers of this one function against each other.
_BOOTSTRAP_LOCK_KEY = 872134001


class DuplicateEmailError(Exception):
    """Raised when the given email is already registered (case-insensitively) -
    callers translate this into a 409."""


def count_users(pool: ConnectionPool) -> int:
    with pool.connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return row["n"]


def create_user(pool: ConnectionPool, email: str, password_hash: str, role: str) -> dict:
    """Raises DuplicateEmailError if the email is already registered
    (case-insensitively, via the users_email_lower_unique index)."""
    user_id = uuid.uuid4().hex
    with pool.connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (user_id, email, password_hash, role),
            )
            conn.commit()
        except psycopg.errors.UniqueViolation as e:
            conn.rollback()
            raise DuplicateEmailError(f"An account with email {email!r} already exists") from e
    return {"id": user_id, "email": email, "role": role}


def create_user_with_bootstrap_role(pool: ConnectionPool, email: str, password_hash: str) -> dict:
    """Same "first account ever becomes admin, everyone after that is viewer"
    rule the register route used to compute via a separate count_users() call
    followed by create_user() - but atomically, via a transaction-scoped
    advisory lock, so two concurrent registrations hitting a fresh deployment
    at once can't both observe zero users and both become admin (the second
    blocks on the lock until the first commits, then correctly sees count=1).
    The lock auto-releases on commit/rollback, so it never outlives this
    transaction even if the connection is later reused from the pool."""
    user_id = uuid.uuid4().hex
    with pool.connection() as conn:
        try:
            conn.execute("SELECT pg_advisory_xact_lock(%s::bigint)", (_BOOTSTRAP_LOCK_KEY,))
            count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            role = "admin" if count == 0 else "viewer"
            conn.execute(
                "INSERT INTO users (id, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (user_id, email, password_hash, role),
            )
            conn.commit()
            return {"id": user_id, "email": email, "role": role}
        except psycopg.errors.UniqueViolation as e:
            conn.rollback()
            raise DuplicateEmailError(f"An account with email {email!r} already exists") from e


def get_user_by_email(pool: ConnectionPool, email: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone()
        return row


def get_user_by_id(pool: ConnectionPool, user_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
        return row


def list_users(pool: ConnectionPool) -> list[dict]:
    """All users, oldest first, for the admin-only user-management page. Rows
    include password_hash (like get_user_by_id) - the route layer is
    responsible for stripping it before returning to the client."""
    with pool.connection() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        return rows


def update_role(pool: ConnectionPool, user_id: str, role: str) -> dict | None:
    """Returns the updated row, or None if user_id doesn't exist. Callers
    must validate `role` themselves (the users_role_check CHECK constraint is
    only the final backstop)."""
    with pool.connection() as conn:
        row = conn.execute(
            "UPDATE users SET role=%s WHERE id=%s RETURNING *", (role, user_id)
        ).fetchone()
        conn.commit()
        return row
