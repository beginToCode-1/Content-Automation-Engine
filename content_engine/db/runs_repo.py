from datetime import datetime
from typing import Any

from psycopg_pool import ConnectionPool


def _platforms_to_str(platforms: list[str]) -> str:
    return ",".join(platforms)


def platforms_from_str(value: str) -> list[str]:
    return [p for p in value.split(",") if p]


def count_all(pool: ConnectionPool, user_id: str | None = None) -> int:
    with pool.connection() as conn:
        if user_id is None:
            row = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM runs WHERE user_id=%s", (user_id,)).fetchone()
        return row["n"]


def insert_run(
    pool: ConnectionPool,
    run_id: str,
    topic: str,
    trigger_source: str,
    target_platforms: list[str],
    dry_run: bool = False,
    requested_privacy: str | None = None,
    schedule_id: int | None = None,
    work_dir: str | None = None,
    user_id: str | None = None,
    youtube_account_id: str | None = None,
) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, user_id, youtube_account_id, topic, trigger_source, schedule_id, status,
                dry_run, requested_privacy, target_platforms, work_dir
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s)
            """,
            (
                run_id,
                user_id,
                youtube_account_id,
                topic,
                trigger_source,
                schedule_id,
                dry_run,
                requested_privacy,
                _platforms_to_str(target_platforms),
                work_dir,
            ),
        )
        conn.commit()


def try_reclaim_failed(pool: ConnectionPool, run_id: str) -> bool:
    """Atomically claims a failed run for retry by flipping it to 'running' only
    if it's still 'failed' - the compare-and-set that stops two concurrent
    /retry requests (double-click, two tabs) from both proceeding to
    re-publish the same run_id."""
    with pool.connection() as conn:
        cursor = conn.execute("UPDATE runs SET status='running' WHERE run_id=%s AND status='failed'", (run_id,))
        conn.commit()
        return cursor.rowcount > 0


def mark_running(pool: ConnectionPool, run_id: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "UPDATE runs SET status='running', started_at=now() WHERE run_id=%s",
            (run_id,),
        )
        conn.commit()


_UPDATABLE_COLUMNS = {
    "user_id", "youtube_account_id", "topic", "trigger_source", "schedule_id", "status",
    "current_stage", "dry_run", "requested_privacy", "effective_privacy", "target_platforms",
    "source_video_id", "source_video_title", "source_video_url", "segment_start_s", "segment_end_s",
    "segment_score", "clip_path", "metadata_title", "metadata_description", "metadata_hashtags",
    "error_message", "work_dir", "started_at", "finished_at", "batch_id", "scheduled_upload_at",
    "source_type", "video_rank", "clip_rank",
}


def update_fields(pool: ConnectionPool, run_id: str, **fields: Any) -> None:
    """`fields` keys become raw SQL column names (values stay parameterized) -
    the allowlist below is what stops a future caller that forwards
    request-derived keys (e.g. **payload.dict()) from injecting arbitrary SQL
    via the column list. Every current caller passes hardcoded literal kwargs."""
    if not fields:
        return
    unknown = set(fields) - _UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"update_fields got unknown runs column(s): {sorted(unknown)}")
    columns = ", ".join(f"{key}=%s" for key in fields)
    values = list(fields.values()) + [run_id]
    with pool.connection() as conn:
        conn.execute(f"UPDATE runs SET {columns} WHERE run_id=%s", values)
        conn.commit()


def mark_succeeded(pool: ConnectionPool, run_id: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE runs SET status='succeeded', error_message=NULL,
                finished_at=now()
            WHERE run_id=%s
            """,
            (run_id,),
        )
        conn.commit()


def mark_failed(pool: ConnectionPool, run_id: str, error_message: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE runs SET status='failed', error_message=%s,
                finished_at=now()
            WHERE run_id=%s
            """,
            (error_message, run_id),
        )
        conn.commit()


def append_event(pool: ConnectionPool, run_id: str, stage: str, message: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO run_events (run_id, stage, message) VALUES (%s, %s, %s)",
            (run_id, stage, message),
        )
        conn.execute("UPDATE runs SET current_stage=%s WHERE run_id=%s", (stage, run_id))
        conn.commit()


def get_run(pool: ConnectionPool, run_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id=%s", (run_id,)).fetchone()
        return row


def list_recent(pool: ConnectionPool, limit: int = 20, user_id: str | None = None) -> list[dict]:
    with pool.connection() as conn:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user_id, limit)
            ).fetchall()
        return rows


def list_events_since(pool: ConnectionPool, run_id: str, since_id: int = 0) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM run_events WHERE run_id=%s AND id>%s ORDER BY id ASC",
            (run_id, since_id),
        ).fetchall()
        return rows


def list_due_queued_uploads(pool: ConnectionPool, now: datetime) -> list[dict]:
    """Runs whose deferred upload time has arrived and that still have at least
    one platform upload waiting (status='pending' in run_uploads)."""
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM runs
            WHERE scheduled_upload_at IS NOT NULL AND scheduled_upload_at <= %s
              AND EXISTS (
                  SELECT 1 FROM run_uploads
                  WHERE run_uploads.run_id = runs.run_id AND run_uploads.status = 'pending'
              )
            """,
            (now_iso,),
        ).fetchall()
        return rows


def list_runs_for_batch(pool: ConnectionPool, batch_id: str) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE batch_id=%s ORDER BY video_rank ASC, clip_rank ASC", (batch_id,)
        ).fetchall()
        return rows


def clear_scheduled_upload(pool: ConnectionPool, run_id: str) -> None:
    with pool.connection() as conn:
        conn.execute("UPDATE runs SET scheduled_upload_at=NULL WHERE run_id=%s", (run_id,))
        conn.commit()


def sweep_stale_running(pool: ConnectionPool) -> int:
    with pool.connection() as conn:
        cursor = conn.execute(
            """
            UPDATE runs SET status='failed',
                error_message='Interrupted by dashboard restart',
                finished_at=now()
            WHERE status IN ('pending','running')
            """
        )
        conn.commit()
        return cursor.rowcount
