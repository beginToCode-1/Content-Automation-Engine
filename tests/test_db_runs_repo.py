from content_engine.db import runs_repo


def test_insert_and_get_run(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "stoicism", "web", ["youtube", "tiktok"])

    row = runs_repo.get_run(pg_pool, "run1")
    assert row["topic"] == "stoicism"
    assert row["status"] == "pending"
    assert runs_repo.platforms_from_str(row["target_platforms"]) == ["youtube", "tiktok"]


def test_mark_running_then_succeeded(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "stoicism", "cli", ["youtube"])

    runs_repo.mark_running(pg_pool, "run1")
    assert runs_repo.get_run(pg_pool, "run1")["status"] == "running"

    runs_repo.mark_succeeded(pg_pool, "run1")
    row = runs_repo.get_run(pg_pool, "run1")
    assert row["status"] == "succeeded"
    assert row["finished_at"] is not None


def test_mark_failed_records_error(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "stoicism", "cli", ["youtube"])

    runs_repo.mark_failed(pg_pool, "run1", "boom")
    row = runs_repo.get_run(pg_pool, "run1")
    assert row["status"] == "failed"
    assert row["error_message"] == "boom"


def test_append_event_and_list_events_since(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "stoicism", "cli", ["youtube"])

    runs_repo.append_event(pg_pool, "run1", "search", "found 5 videos")
    runs_repo.append_event(pg_pool, "run1", "download", "downloaded")

    all_events = runs_repo.list_events_since(pg_pool, "run1", since_id=0)
    assert [e["stage"] for e in all_events] == ["search", "download"]

    later_events = runs_repo.list_events_since(pg_pool, "run1", since_id=all_events[0]["id"])
    assert [e["stage"] for e in later_events] == ["download"]

    assert runs_repo.get_run(pg_pool, "run1")["current_stage"] == "download"


def test_list_recent_orders_newest_first(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "topic1", "cli", ["youtube"])
    runs_repo.insert_run(pg_pool, "run2", "topic2", "cli", ["youtube"])

    recent = runs_repo.list_recent(pg_pool)
    assert [r["run_id"] for r in recent] == ["run2", "run1"]


def test_sweep_stale_running_marks_pending_and_running_as_failed(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "topic1", "cli", ["youtube"])
    runs_repo.insert_run(pg_pool, "run2", "topic2", "cli", ["youtube"])
    runs_repo.mark_running(pg_pool, "run2")
    runs_repo.mark_succeeded(pg_pool, "run2")

    runs_repo.insert_run(pg_pool, "run3", "topic3", "cli", ["youtube"])
    runs_repo.mark_running(pg_pool, "run3")

    swept = runs_repo.sweep_stale_running(pg_pool)
    assert swept == 2

    assert runs_repo.get_run(pg_pool, "run1")["status"] == "failed"
    assert runs_repo.get_run(pg_pool, "run2")["status"] == "succeeded"
    assert runs_repo.get_run(pg_pool, "run3")["status"] == "failed"


def test_try_reclaim_failed_only_succeeds_when_status_is_failed(pg_pool):
    runs_repo.insert_run(pg_pool, "run1", "topic1", "cli", ["youtube"])

    assert runs_repo.try_reclaim_failed(pg_pool, "run1") is False

    runs_repo.mark_failed(pg_pool, "run1", "boom")
    assert runs_repo.try_reclaim_failed(pg_pool, "run1") is True
    assert runs_repo.get_run(pg_pool, "run1")["status"] == "running"

    # already reclaimed once - a second concurrent attempt must not also succeed
    runs_repo.mark_failed(pg_pool, "run1", "boom again")
    assert runs_repo.try_reclaim_failed(pg_pool, "run1") is True
    runs_repo.mark_running(pg_pool, "run1")
    assert runs_repo.try_reclaim_failed(pg_pool, "run1") is False
