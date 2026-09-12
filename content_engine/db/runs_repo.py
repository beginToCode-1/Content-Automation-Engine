from datetime import datetime
from pathlib import Path
from typing import Any

from content_engine.db.connection import get_connection


def _platforms_to_str(platforms: list[str]) -> str:
    return ",".join(platforms)


def platforms_from_str(value: str) -> list[str]:
    return [p for p in value.split(",") if p]


def count_all(db_path: Path, user_id: str | None = None) -> int:
    conn = get_connection(db_path)
    try:
        if user_id is None:
            row = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM runs WHERE user_id=?", (user_id,)).fetchone()
        return row["n"]
    finally:
        conn.close()


def insert_run(
    db_path: Path,
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
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, user_id, youtube_account_id, topic, trigger_source, schedule_id, status,
                dry_run, requested_privacy, target_platforms, work_dir
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                run_id,
                user_id,
                youtube_account_id,
                topic,
                trigger_source,
                schedule_id,
                int(dry_run),
                requested_privacy,
                _platforms_to_str(target_platforms),
                work_dir,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def try_reclaim_failed(db_path: Path, run_id: str) -> bool:
    """Atomically claims a failed run for retry by flipping it to 'running' only
    if it's still 'failed' - the compare-and-set that stops two concurrent
    /retry requests (double-click, two tabs) from both proceeding to
    re-publish the same run_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("UPDATE runs SET status='running' WHERE run_id=? AND status='failed'", (run_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def mark_running(db_path: Path, run_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE runs SET status='running', started_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE run_id=?",
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()


_UPDATABLE_COLUMNS = {
    "user_id", "youtube_account_id", "topic", "trigger_source", "schedule_id", "status",
    "current_stage", "dry_run", "requested_privacy", "effective_privacy", "target_platforms",
    "source_video_id", "source_video_title", "source_video_url", "segment_start_s", "segment_end_s",
    "segment_score", "clip_path", "metadata_title", "metadata_description", "metadata_hashtags",
    "error_message", "work_dir", "started_at", "finished_at", "batch_id", "scheduled_upload_at",
    "source_type", "video_rank", "clip_rank",
}


def update_fields(db_path: Path, run_id: str, **fields: Any) -> None:
    """`fields` keys become raw SQL column names (values stay parameterized) -
    the allowlist below is what stops a future caller that forwards
    request-derived keys (e.g. **payload.dict()) from injecting arbitrary SQL
    via the column list. Every current caller passes hardcoded literal kwargs."""
    if not fields:
        return
    unknown = set(fields) - _UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"update_fields got unknown runs column(s): {sorted(unknown)}")
    columns = ", ".join(f"{key}=?" for key in fields)
    values = list(fields.values()) + [run_id]
    conn = get_connection(db_path)
    try:
        conn.execute(f"UPDATE runs SET {columns} WHERE run_id=?", values)
        conn.commit()
    finally:
        conn.close()


def mark_succeeded(db_path: Path, run_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE runs SET status='succeeded', error_message=NULL,
                finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE run_id=?
            """,
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()


def mark_failed(db_path: Path, run_id: str, error_message: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE runs SET status='failed', error_message=?,
                finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE run_id=?
            """,
            (error_message, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def append_event(db_path: Path, run_id: str, stage: str, message: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO run_events (run_id, stage, message) VALUES (?, ?, ?)",
            (run_id, stage, message),
        )
        conn.execute("UPDATE runs SET current_stage=? WHERE run_id=?", (stage, run_id))
        conn.commit()
    finally:
        conn.close()


def get_run(db_path: Path, run_id: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_recent(db_path: Path, limit: int = 20, user_id: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_events_since(db_path: Path, run_id: str, since_id: int = 0) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM run_events WHERE run_id=? AND id>? ORDER BY id ASC",
            (run_id, since_id),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_due_queued_uploads(db_path: Path, now: datetime) -> list[dict]:
    """Runs whose deferred upload time has arrived and that still have at least
    one platform upload waiting (status='pending' in run_uploads)."""
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM runs
            WHERE scheduled_upload_at IS NOT NULL AND scheduled_upload_at <= ?
              AND EXISTS (
                  SELECT 1 FROM run_uploads
                  WHERE run_uploads.run_id = runs.run_id AND run_uploads.status = 'pending'
              )
            """,
            (now_iso,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_runs_for_batch(db_path: Path, batch_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM runs WHERE batch_id=? ORDER BY video_rank ASC, clip_rank ASC", (batch_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def clear_scheduled_upload(db_path: Path, run_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE runs SET scheduled_upload_at=NULL WHERE run_id=?", (run_id,))
        conn.commit()
    finally:
        conn.close()


def sweep_stale_running(db_path: Path) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE runs SET status='failed',
                error_message='Interrupted by dashboard restart',
                finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE status IN ('pending','running')
            """
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
