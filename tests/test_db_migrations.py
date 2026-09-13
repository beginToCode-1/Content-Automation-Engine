from content_engine.db import connection


def test_init_db_creates_all_expected_tables(pg_pool):
    with pg_pool.connection() as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()
    tables = {r["table_name"] for r in rows}
    for expected in (
        "users",
        "connected_accounts",
        "run_batches",
        "scheduled_topics",
        "runs",
        "run_events",
        "run_uploads",
        "schema_migrations",
    ):
        assert expected in tables


def test_init_db_is_idempotent(pg_pool):
    # pg_pool's own setup already called init_db() once via the session-scoped
    # _pool fixture - calling it again here must not raise (e.g. "relation
    # already exists" or "constraint already exists").
    connection.init_db(pg_pool)
    connection.init_db(pg_pool)


def test_users_email_unique_index_is_case_insensitive(pg_pool):
    with pg_pool.connection() as conn:
        rows = conn.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename='users'"
        ).fetchall()
    assert any(r["indexname"] == "users_email_lower_unique" for r in rows)


def test_no_migrations_directory_or_empty_leaves_schema_migrations_untouched(pg_pool):
    with pg_pool.connection() as conn:
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    # No migrations/*.sql files exist yet in this repo - schema_migrations
    # stays empty until the first real forward migration is added.
    assert rows == []
