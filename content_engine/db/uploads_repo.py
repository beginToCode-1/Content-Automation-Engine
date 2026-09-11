from pathlib import Path

from content_engine.db.connection import get_connection
from content_engine.models import PlatformUploadOutcome


def upsert_upload_outcome(
    db_path: Path,
    run_id: str,
    platform: str,
    status: str,
    video_id: str | None = None,
    url: str | None = None,
    privacy_status: str | None = None,
    error_message: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO run_uploads (run_id, platform, status, video_id, url, privacy_status, error_message, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            ON CONFLICT(run_id, platform) DO UPDATE SET
                status=excluded.status,
                video_id=excluded.video_id,
                url=excluded.url,
                privacy_status=excluded.privacy_status,
                error_message=excluded.error_message,
                finished_at=excluded.finished_at
            """,
            (run_id, platform, status, video_id, url, privacy_status, error_message),
        )
        conn.commit()
    finally:
        conn.close()


def record_upload_outcomes(db_path: Path, run_id: str, outcomes: list[PlatformUploadOutcome]) -> None:
    for outcome in outcomes:
        upsert_upload_outcome(
            db_path,
            run_id,
            outcome.platform,
            status="succeeded" if outcome.result else "failed",
            video_id=outcome.result.video_id if outcome.result else None,
            url=outcome.result.url if outcome.result else None,
            privacy_status=outcome.result.privacy_status if outcome.result else None,
            error_message=outcome.error,
        )


def insert_pending_uploads(db_path: Path, run_id: str, platforms: list[str]) -> None:
    """Pre-creates 'pending' rows for a run whose upload is deferred to a later
    scheduled time - lets list_due_queued_uploads() find it before any upload
    attempt has actually happened."""
    conn = get_connection(db_path)
    try:
        for platform in platforms:
            conn.execute(
                """
                INSERT INTO run_uploads (run_id, platform, status)
                VALUES (?, ?, 'pending')
                ON CONFLICT(run_id, platform) DO NOTHING
                """,
                (run_id, platform),
            )
        conn.commit()
    finally:
        conn.close()


def mark_uploading(db_path: Path, run_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE run_uploads SET status='uploading' WHERE run_id=? AND status='pending'", (run_id,)
        )
        conn.commit()
    finally:
        conn.close()


def skip_pending_uploads(db_path: Path, run_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE run_uploads SET status='skipped' WHERE run_id=? AND status='pending'", (run_id,)
        )
        conn.commit()
    finally:
        conn.close()


def sweep_stale_uploading(db_path: Path) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE run_uploads SET status='failed',
                error_message='Interrupted by dashboard restart',
                finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE status='uploading'
            """
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def list_uploads_for_run(db_path: Path, run_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM run_uploads WHERE run_id=? ORDER BY id ASC", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
