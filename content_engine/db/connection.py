from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Every table this schema creates, in an order safe for TRUNCATE ... CASCADE
# (doesn't actually matter with CASCADE, but kept alphabetical-by-dependency
# for readability). Used by the test suite to reset state between tests.
_ALL_TABLES = [
    "run_events",
    "run_uploads",
    "runs",
    "scheduled_topics",
    "run_batches",
    "connected_accounts",
    "users",
]

_pool: ConnectionPool | None = None


def init_pool(database_url: str) -> ConnectionPool:
    """Creates the process-wide connection pool if it doesn't exist yet, or
    returns the existing one. Safe to call more than once (tests call this
    every session; app startup calls it once) - only the first call's
    database_url takes effect.

    prepare_threshold=None disables psycopg3's default server-side prepared
    statements: Supabase's session pooler proxies a persistent connection
    for IPv4 compatibility, but some poolers/proxies in this chain don't
    guarantee the same backend across reconnects, so prepared statements are
    disabled defensively rather than relied upon.
    """
    global _pool
    if _pool is not None:
        return _pool
    _pool = ConnectionPool(
        conninfo=database_url,
        min_size=0,
        max_size=5,
        kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": False},
        open=True,
    )
    return _pool


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized - call connection.init_pool(database_url) first"
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def init_db(pool: ConnectionPool) -> None:
    """Applies schema.sql (idempotent - safe to run on every app startup),
    then any numbered migrations/*.sql not yet recorded in schema_migrations.
    schema.sql itself creates the schema_migrations table, so it's applied
    unconditionally first; every file under migrations/ is version-tracked
    from then on."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with pool.connection() as conn:
        conn.execute(schema)
        conn.commit()

        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql")) if _MIGRATIONS_DIR.is_dir() else []
        for path in migration_files:
            version = int(path.name.split("_", 1)[0])
            if version in applied:
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )
            conn.commit()


def truncate_all_tables(pool: ConnectionPool) -> None:
    """Test-only helper: wipes every table and resets identity sequences, so
    each test starts from a clean, predictable database. CASCADE is required
    because of the FK web between these tables; RESTART IDENTITY resets the
    run_events/run_uploads/scheduled_topics auto-incrementing ids to 1."""
    with pool.connection() as conn:
        tables = ", ".join(_ALL_TABLES)
        conn.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
        conn.commit()
