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


def test_second_retry_of_the_same_run_is_refused(client):
    admin = _register(client, "admin@example.com")
    from content_engine.db import connection, runs_repo

    pool = connection.get_pool()
    runs_repo.insert_run(pool, "r-dbl", "topic", "web", ["youtube"], user_id=admin["user"]["id"])
    runs_repo.mark_failed(pool, "r-dbl", "boom")
    headers = _auth_headers(admin["access_token"])

    with patch("content_engine.webapp.routes.api_runs.executor.submit_run", return_value="new-run") as submit:
        first = client.post("/api/runs/r-dbl/retry", headers=headers)
        second = client.post("/api/runs/r-dbl/retry", headers=headers)

    assert first.status_code == 202 and second.status_code == 409
    submit.assert_called_once()
    assert runs_repo.get_run(pool, "r-dbl")["retried_as"] == "new-run"


def test_failed_retry_start_releases_the_claim(client):
    admin = _register(client, "admin@example.com")
    from content_engine.db import connection, runs_repo

    pool = connection.get_pool()
    runs_repo.insert_run(pool, "r-err", "topic", "web", ["youtube"], user_id=admin["user"]["id"])
    runs_repo.mark_failed(pool, "r-err", "boom")
    with patch("content_engine.webapp.routes.api_runs.executor.submit_run", side_effect=RuntimeError("down")):
        try:
            client.post("/api/runs/r-err/retry", headers=_auth_headers(admin["access_token"]))
        except RuntimeError:
            pass
    assert runs_repo.get_run(pool, "r-err")["retried_as"] is None
