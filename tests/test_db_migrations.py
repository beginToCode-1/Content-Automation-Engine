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


def test_migrations_are_applied_and_recorded_exactly_once(pg_pool):
    with pg_pool.connection() as conn:
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    # 0001_add_cancelled_run_status.sql is this repo's first real forward
    # migration - pg_pool's session-scoped setup (init_db, via conftest.py)
    # already applied it once, so it should be recorded exactly once here,
    # not reapplied or duplicated by any later init_db() call in this test run.
    assert [r["version"] for r in rows] == [1]
