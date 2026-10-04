from unittest.mock import patch

from tests.test_api_users import _auth_headers, _register, client  # noqa: F401  (fixture)


def test_retry_keeps_dry_run_and_forced_private(client):
    admin = _register(client, "admin@example.com")
    from content_engine.db import connection, runs_repo

    pool = connection.get_pool()
    runs_repo.insert_run(pool, "sched-run", "topic", "scheduled", ["tiktok"], dry_run=True, user_id=admin["user"]["id"])
    runs_repo.mark_failed(pool, "sched-run", "boom")

    with patch("content_engine.webapp.routes.api_runs.executor.submit_run", return_value="new-run") as submit:
        res = client.post("/api/runs/sched-run/retry", headers=_auth_headers(admin["access_token"]))

    assert res.status_code == 202, res.text
    kwargs = submit.call_args.kwargs
    assert kwargs["dry_run"] is True
    assert kwargs["force_private"] is True


def test_cancelled_run_can_be_reclaimed_for_retry(pg_pool):
    from content_engine.db import runs_repo

    runs_repo.insert_run(pg_pool, "r1", "topic", "web", ["youtube"])
    runs_repo.update_fields(pg_pool, "r1", status="cancelled")
    assert runs_repo.try_reclaim_failed(pg_pool, "r1") is True
    assert runs_repo.try_reclaim_failed(pg_pool, "r1") is False  # second click loses
