from datetime import datetime
from pathlib import Path

from content_engine.db.connection import get_connection


def insert_schedule(
    db_path: Path,
    topic: str,
    recurrence: str,
    target_platforms: list[str],
    scheduled_time: str | None = None,
    daily_time: str | None = None,
) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO scheduled_topics (topic, recurrence, scheduled_time, daily_time, target_platforms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (topic, recurrence, scheduled_time, daily_time, ",".join(target_platforms)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_active(db_path: Path) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_topics WHERE status != 'cancelled' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def find_due(db_path: Path, now: datetime) -> list[dict]:
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    today = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H:%M")

    conn = get_connection(db_path)
    try:
        once_rows = conn.execute(
            """
            SELECT * FROM scheduled_topics
            WHERE status='active' AND recurrence='once' AND scheduled_time <= ?
            """,
            (now_iso,),
        ).fetchall()

        daily_rows = conn.execute(
            """
            SELECT * FROM scheduled_topics
            WHERE status='active' AND recurrence='daily' AND daily_time <= ?
              AND (last_triggered_at IS NULL OR substr(last_triggered_at, 1, 10) < ?)
            """,
            (hhmm, today),
        ).fetchall()

        return [dict(row) for row in [*once_rows, *daily_rows]]
    finally:
        conn.close()


def mark_triggered(db_path: Path, schedule_id: int, run_id: str, now: datetime) -> None:
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE scheduled_topics SET last_triggered_at=?, last_run_id=? WHERE id=?",
            (now_iso, run_id, schedule_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_completed(db_path: Path, schedule_id: int) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE scheduled_topics SET status='completed' WHERE id=?", (schedule_id,))
        conn.commit()
    finally:
        conn.close()


def cancel(db_path: Path, schedule_id: int) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE scheduled_topics SET status='cancelled' WHERE id=?", (schedule_id,))
        conn.commit()
    finally:
        conn.close()
