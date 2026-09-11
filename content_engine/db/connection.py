import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Additive column migrations for tables that already existed before these
# columns were introduced. Each entry is (table, column, ddl-after-column-name).
# Guarded by a PRAGMA table_info check so this is safe to run against both a
# fresh database (schema.sql already includes these, so nothing to add) and an
# existing populated one (no CHECK-constraint changes, no table rebuild - just
# new nullable columns, which SQLite allows adding without touching existing rows).
_ADDITIVE_COLUMNS = [
    ("runs", "batch_id", "TEXT REFERENCES run_batches(batch_id)"),
    ("runs", "scheduled_upload_at", "TEXT"),
    ("runs", "source_type", "TEXT"),
    ("runs", "video_rank", "INTEGER"),
    ("runs", "clip_rank", "INTEGER"),
]


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _apply_additive_migrations(conn: sqlite3.Connection) -> None:
    for table, column, ddl in _ADDITIVE_COLUMNS:
        existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_batch ON runs(batch_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_scheduled_upload ON runs(scheduled_upload_at)")


def init_db(db_path: Path) -> None:
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(schema)
        _apply_additive_migrations(conn)
        conn.commit()
    finally:
        conn.close()
