import uuid
from pathlib import Path

from content_engine.auth.token_crypto import decrypt_token, encrypt_token
from content_engine.db.connection import get_connection


def upsert_account(
    db_path: Path,
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
    conn = get_connection(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM connected_accounts WHERE user_id=? AND platform=? AND external_account_id=?",
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
                SET account_label=?, access_token=?, refresh_token=COALESCE(?, refresh_token),
                    token_expiry=?, scopes=?
                WHERE id=?
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    finally:
        conn.close()


def update_tokens(
    db_path: Path,
    encryption_key: str,
    account_id: str,
    access_token: str,
    token_expiry: str | None,
    refresh_token: str | None = None,
) -> None:
    """Called after a credential refresh - Google may or may not issue a new
    refresh_token on refresh, so that field is only overwritten when one is
    actually given back (None means "keep the existing one")."""
    conn = get_connection(db_path)
    try:
        enc_access = encrypt_token(encryption_key, access_token)
        if refresh_token:
            conn.execute(
                "UPDATE connected_accounts SET access_token=?, token_expiry=?, refresh_token=? WHERE id=?",
                (enc_access, token_expiry, encrypt_token(encryption_key, refresh_token), account_id),
            )
        else:
            conn.execute(
                "UPDATE connected_accounts SET access_token=?, token_expiry=? WHERE id=?",
                (enc_access, token_expiry, account_id),
            )
        conn.commit()
    finally:
        conn.close()


def _decrypt_row(row: dict, encryption_key: str) -> dict:
    row = dict(row)
    row["access_token"] = decrypt_token(encryption_key, row["access_token"])
    row["refresh_token"] = decrypt_token(encryption_key, row["refresh_token"]) if row["refresh_token"] else None
    row["scopes"] = [s for s in row["scopes"].split(",") if s]
    return row


def get_account(db_path: Path, account_id: str, encryption_key: str) -> dict | None:
    """Returns the row WITH decrypted tokens - only call this right before
    building API credentials, never to display to a user."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM connected_accounts WHERE id=?", (account_id,)).fetchone()
        return _decrypt_row(row, encryption_key) if row else None
    finally:
        conn.close()


def list_accounts_public(db_path: Path, user_id: str, platform: str | None = None) -> list[dict]:
    """Returns rows WITHOUT token fields - safe to send straight to the frontend."""
    conn = get_connection(db_path)
    try:
        if platform:
            rows = conn.execute(
                "SELECT id, platform, account_label, external_account_id, created_at "
                "FROM connected_accounts WHERE user_id=? AND platform=? ORDER BY created_at ASC",
                (user_id, platform),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, platform, account_label, external_account_id, created_at "
                "FROM connected_accounts WHERE user_id=? ORDER BY created_at ASC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_account_public(db_path: Path, account_id: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id, user_id, platform, account_label, external_account_id, created_at "
            "FROM connected_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_account(db_path: Path, account_id: str, user_id: str) -> bool:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "DELETE FROM connected_accounts WHERE id=? AND user_id=?", (account_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
