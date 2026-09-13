from psycopg_pool import ConnectionPool


def insert_batch(
    pool: ConnectionPool,
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
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO run_batches (
                batch_id, user_id, youtube_account_id, topic, target_platforms, videos_count, clips_per_video,
                stagger_gap_minutes, requested_privacy
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def mark_batch_finished(pool: ConnectionPool, batch_id: str, status: str, error_message: str | None = None) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE run_batches SET status=%s, error_message=%s,
                finished_at=now()
            WHERE batch_id=%s
            """,
            (status, error_message, batch_id),
        )
        conn.commit()


def get_batch(pool: ConnectionPool, batch_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM run_batches WHERE batch_id=%s", (batch_id,)).fetchone()
        return row


def list_recent_batches(pool: ConnectionPool, limit: int = 20, user_id: str | None = None) -> list[dict]:
    with pool.connection() as conn:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM run_batches ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM run_batches WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user_id, limit)
            ).fetchall()
        return rows
