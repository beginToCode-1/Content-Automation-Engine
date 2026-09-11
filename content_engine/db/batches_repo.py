from pathlib import Path

from content_engine.db.connection import get_connection


def insert_batch(
    db_path: Path,
    batch_id: str,
    topic: str,
    target_platforms: list[str],
    videos_count: int,
    clips_per_video: int,
    stagger_gap_minutes: int,
    requested_privacy: str | None = None,
    user_id: str | None = None,
    youtube_account_id: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO run_batches (
                batch_id, user_id, youtube_account_id, topic, target_platforms, videos_count, clips_per_video,
                stagger_gap_minutes, requested_privacy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                user_id,
                youtube_account_id,
                topic,
                ",".join(target_platforms),
                videos_count,
                clips_per_video,
                stagger_gap_minutes,
                requested_privacy,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def mark_batch_finished(db_path: Path, batch_id: str, status: str, error_message: str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE run_batches SET status=?, error_message=?,
                finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE batch_id=?
            """,
            (status, error_message, batch_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_batch(db_path: Path, batch_id: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM run_batches WHERE batch_id=?", (batch_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_recent_batches(db_path: Path, limit: int = 20, user_id: str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM run_batches ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM run_batches WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
