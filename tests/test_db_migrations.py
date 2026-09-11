import sqlite3

from content_engine.db.connection import get_connection, init_db

_OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    trigger_source TEXT NOT NULL CHECK(trigger_source IN ('cli','web','scheduled')),
    schedule_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','failed')),
    current_stage TEXT,
    dry_run INTEGER NOT NULL DEFAULT 0,
    requested_privacy TEXT,
    effective_privacy TEXT,
    target_platforms TEXT NOT NULL DEFAULT 'youtube',
    source_video_id TEXT,
    source_video_title TEXT,
    source_video_url TEXT,
    segment_start_s REAL,
    segment_end_s REAL,
    segment_score REAL,
    clip_path TEXT,
    metadata_title TEXT,
    metadata_description TEXT,
    metadata_hashtags TEXT,
    error_message TEXT,
    work_dir TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    started_at TEXT,
    finished_at TEXT
);
"""


def _seed_old_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_OLD_SCHEMA)
    conn.execute(
        "INSERT INTO runs (run_id, topic, trigger_source, target_platforms) VALUES (?, ?, ?, ?)",
        ("old_run_1", "a real pre-existing topic", "web", "youtube"),
    )
    conn.commit()
    conn.close()


def test_init_db_adds_new_columns_without_touching_existing_data(tmp_path):
    db_path = tmp_path / "existing.db"
    _seed_old_db(db_path)

    init_db(db_path)

    conn = get_connection(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        for new_column in ("batch_id", "scheduled_upload_at", "source_type", "video_rank", "clip_rank"):
            assert new_column in columns

        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", ("old_run_1",)).fetchone()
        assert row["topic"] == "a real pre-existing topic"
        assert row["trigger_source"] == "web"
        assert row["batch_id"] is None
        assert row["scheduled_upload_at"] is None
    finally:
        conn.close()


def test_init_db_is_idempotent_on_an_already_migrated_db(tmp_path):
    db_path = tmp_path / "fresh.db"
    init_db(db_path)
    init_db(db_path)  # must not raise (e.g. "duplicate column") on a second call

    conn = get_connection(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        assert "batch_id" in columns
    finally:
        conn.close()


def test_init_db_creates_run_batches_table(tmp_path):
    db_path = tmp_path / "fresh2.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "run_batches" in tables
    finally:
        conn.close()
