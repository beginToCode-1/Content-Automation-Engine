import os

import pytest
from dotenv import load_dotenv

from content_engine.db import connection

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


@pytest.fixture(scope="session")
def _pool():
    """One shared pool for the whole test session, pointed at whatever
    DATABASE_URL is configured (the content-engine-dev Supabase project in
    local dev). Session-scoped and NOT autouse - only tests that actually
    touch the database pay the connection/init cost."""
    pool = connection.init_pool(os.environ["DATABASE_URL"])
    connection.init_db(pool)
    yield pool
    connection.close_pool()


@pytest.fixture
def pg_pool(_pool):
    """Function-scoped: truncates every table before each test that requests
    this fixture, replacing what a fresh SQLite file per test used to give
    for free. Deliberately not autouse at the suite level - tests unrelated
    to the database (ffmpeg, scoring, uploaders, etc.) never touch Postgres
    at all."""
    connection.truncate_all_tables(_pool)
    yield _pool
