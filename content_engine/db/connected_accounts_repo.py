import uuid

import psycopg
from psycopg_pool import ConnectionPool

from content_engine.auth.token_crypto import decrypt_token, encrypt_token


class AccountInUseError(Exception):
    """Raised when disconnecting an account is blocked by runs/batches/schedules
    that still reference it (a foreign-key constraint violation)."""


def upsert_account(
    pool: ConnectionPool,
    encryption_key: str,
    user_id: str,
    platform: str,
    account_label: str,
    external_account_id: str,
    access_token: str,
    refresh_token: str | None,
    token_expiry: str | None,
    scopes: list[str],
) -> str:
    """Reconnecting the same external account (same user+platform+external id)
    just refreshes its stored tokens/label in place rather than creating a
    duplicate row - keyed off the UNIQUE(user_id, platform, external_account_id)
    constraint."""
    with pool.connection() as conn:
        existing = conn.execute(
            "SELECT id FROM connected_accounts WHERE user_id=%s AND platform=%s AND external_account_id=%s",
            (user_id, platform, external_account_id),
        ).fetchone()

        enc_access = encrypt_token(encryption_key, access_token)
        enc_refresh = encrypt_token(encryption_key, refresh_token) if refresh_token else None
        scopes_str = ",".join(scopes)

        if existing:
            account_id = existing["id"]
            conn.execute(
                """
                UPDATE connected_accounts
                SET account_label=%s, access_token=%s, refresh_token=COALESCE(%s, refresh_token),
                    token_expiry=%s, scopes=%s
                WHERE id=%s
                """,
                (account_label, enc_access, enc_refresh, token_expiry, scopes_str, account_id),
            )
        else:
            account_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO connected_accounts (
                    id, user_id, platform, account_label, external_account_id,
                    access_token, refresh_token, token_expiry, scopes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    account_id,
                    user_id,
                    platform,
                    account_label,
                    external_account_id,
                    enc_access,
                    enc_refresh,
                    token_expiry,
                    scopes_str,
                ),
            )
        conn.commit()
        return account_id


def update_tokens(
    pool: ConnectionPool,
    encryption_key: str,
    account_id: str,
    access_token: str,
    token_expiry: str | None,
    refresh_token: str | None = None,
) -> None:
    """Called after a credential refresh - Google may or may not issue a new
    refresh_token on refresh, so that field is only overwritten when one is
    actually given back (None means "keep the existing one")."""
    with pool.connection() as conn:
        enc_access = encrypt_token(encryption_key, access_token)
        if refresh_token:
            conn.execute(
                "UPDATE connected_accounts SET access_token=%s, token_expiry=%s, refresh_token=%s WHERE id=%s",
                (enc_access, token_expiry, encrypt_token(encryption_key, refresh_token), account_id),
            )
        else:
            conn.execute(
                "UPDATE connected_accounts SET access_token=%s, token_expiry=%s WHERE id=%s",
                (enc_access, token_expiry, account_id),
            )
        conn.commit()


def _decrypt_row(row: dict, encryption_key: str) -> dict:
    row = dict(row)
    row["access_token"] = decrypt_token(encryption_key, row["access_token"])
    row["refresh_token"] = decrypt_token(encryption_key, row["refresh_token"]) if row["refresh_token"] else None
    row["scopes"] = [s for s in row["scopes"].split(",") if s]
    return row


def get_account(pool: ConnectionPool, account_id: str, encryption_key: str) -> dict | None:
    """Returns the row WITH decrypted tokens - only call this right before
    building API credentials, never to display to a user."""
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM connected_accounts WHERE id=%s", (account_id,)).fetchone()
        return _decrypt_row(row, encryption_key) if row else None


def list_accounts_public(pool: ConnectionPool, user_id: str, platform: str | None = None) -> list[dict]:
    """Returns rows WITHOUT token fields - safe to send straight to the frontend."""
    with pool.connection() as conn:
        if platform:
            rows = conn.execute(
                "SELECT id, platform, account_label, external_account_id, created_at "
                "FROM connected_accounts WHERE user_id=%s AND platform=%s ORDER BY created_at ASC",
                (user_id, platform),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, platform, account_label, external_account_id, created_at "
                "FROM connected_accounts WHERE user_id=%s ORDER BY created_at ASC",
                (user_id,),
            ).fetchall()
        return rows


def delete_account(pool: ConnectionPool, account_id: str, user_id: str) -> bool:
    """Raises AccountInUseError (instead of a raw driver exception) if any
    run/batch/schedule still references this account - those hold a foreign
    key on connected_accounts with no ON DELETE clause, so a straight DELETE
    for a still-referenced row would otherwise 500."""
    with pool.connection() as conn:
        try:
            cursor = conn.execute(
                "DELETE FROM connected_accounts WHERE id=%s AND user_id=%s", (account_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except psycopg.errors.ForeignKeyViolation as e:
            conn.rollback()
            raise AccountInUseError(
                "This account is still referenced by an existing run, batch, or schedule."
            ) from e
