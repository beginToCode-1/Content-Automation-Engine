from datetime import datetime

from psycopg_pool import ConnectionPool


def insert_schedule(
    pool: ConnectionPool,
    topic: str,
    recurrence: str,
    target_platforms: list[str],
    scheduled_time: str | None = None,
    daily_time: str | None = None,
    user_id: str | None = None,
    youtube_account_id: str | None = None,
) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO scheduled_topics (
                user_id, youtube_account_id, topic, recurrence, scheduled_time, daily_time, target_platforms
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, youtube_account_id, topic, recurrence, scheduled_time, daily_time, ",".join(target_platforms)),
        ).fetchone()
        conn.commit()
        return row["id"]


def list_active(pool: ConnectionPool, user_id: str | None = None) -> list[dict]:
    with pool.connection() as conn:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM scheduled_topics WHERE status != 'cancelled' ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scheduled_topics WHERE status != 'cancelled' AND user_id=%s ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return rows


def find_due(pool: ConnectionPool, now: datetime) -> list[dict]:
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    today = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H:%M")

    with pool.connection() as conn:
        once_rows = conn.execute(
            """
            SELECT * FROM scheduled_topics
            WHERE status='active' AND recurrence='once' AND scheduled_time <= %s
            """,
            (now_iso,),
        ).fetchall()

        daily_rows = conn.execute(
            """
            SELECT * FROM scheduled_topics
            WHERE status='active' AND recurrence='daily' AND daily_time <= %s
              AND (last_triggered_at IS NULL OR last_triggered_at::date < %s::date)
            """,
            (hhmm, today),
        ).fetchall()

        return [*once_rows, *daily_rows]


def mark_triggered(pool: ConnectionPool, schedule_id: int, run_id: str, now: datetime) -> None:
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with pool.connection() as conn:
        conn.execute(
            "UPDATE scheduled_topics SET last_triggered_at=%s, last_run_id=%s WHERE id=%s",
            (now_iso, run_id, schedule_id),
        )
        conn.commit()


def mark_completed(pool: ConnectionPool, schedule_id: int) -> None:
    with pool.connection() as conn:
        conn.execute("UPDATE scheduled_topics SET status='completed' WHERE id=%s", (schedule_id,))
        conn.commit()


def cancel(pool: ConnectionPool, schedule_id: int, user_id: str | None = None) -> bool:
    """Returns False (no-op) if schedule_id doesn't exist or belongs to a
    different user_id - callers scoping by user should treat False as a 404,
    not a 500, to avoid leaking whether another user's schedule exists."""
    with pool.connection() as conn:
        if user_id is None:
            cursor = conn.execute("UPDATE scheduled_topics SET status='cancelled' WHERE id=%s", (schedule_id,))
        else:
            cursor = conn.execute(
                "UPDATE scheduled_topics SET status='cancelled' WHERE id=%s AND user_id=%s", (schedule_id, user_id)
            )
        conn.commit()
        return cursor.rowcount > 0
