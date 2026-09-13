from fastapi import HTTPException
from psycopg_pool import ConnectionPool

from content_engine.db import connected_accounts_repo


def resolve_youtube_account_id(
    pool: ConnectionPool, user: dict, platforms: list[str], requested_account_id: str | None
) -> str | None:
    """Figures out which of the current user's connected YouTube accounts a
    new run/batch/schedule should publish to, or raises a 400 with a message
    the frontend can show directly. Returns None when "youtube" isn't even
    one of the requested platforms - nothing to resolve.

    - An explicit `requested_account_id` must belong to this user (checked
      here, not left to the DB layer, so a wrong id 400s instead of silently
      publishing to whatever get_youtube_client_for_account happens to load).
    - With none given: auto-select if the user has exactly one connected
      account, otherwise 400 (zero connected, or ambiguous with 2+).
    """
    if "youtube" not in platforms:
        return None

    accounts = connected_accounts_repo.list_accounts_public(pool, user["id"], "youtube")

    if requested_account_id:
        if not any(a["id"] == requested_account_id for a in accounts):
            raise HTTPException(status_code=400, detail="That YouTube account isn't connected to your account")
        return requested_account_id

    if len(accounts) == 1:
        return accounts[0]["id"]
    if len(accounts) == 0:
        raise HTTPException(
            status_code=400, detail="Connect a YouTube account first (Connected Accounts page)"
        )
    raise HTTPException(
        status_code=400,
        detail="You have multiple YouTube accounts connected - specify which one (youtube_account_id)",
    )
