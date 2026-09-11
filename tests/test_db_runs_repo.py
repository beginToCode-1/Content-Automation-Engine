from content_engine.db.connection import init_db
from content_engine.db import runs_repo


def _fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_insert_and_get_run(tmp_path):
    db_path = _fresh_db(tmp_path)
    runs_repo.insert_run(db_path, "run1", "stoicism", "web", ["youtube", "tiktok"])

    row = runs_repo.get_run(db_path, "run1")
    assert row["topic"] == "stoicism"
    assert row["status"] == "pending"
    assert runs_repo.platforms_from_str(row["target_platforms"]) == ["youtube", "tiktok"]


def test_mark_running_then_succeeded(tmp_path):
    db_path = _fresh_db(tmp_path)
    runs_repo.insert_run(db_path, "run1", "stoicism", "cli", ["youtube"])

    runs_repo.mark_running(db_path, "run1")
    assert runs_repo.get_run(db_path, "run1")["status"] == "running"

    runs_repo.mark_succeeded(db_path, "run1")
    row = runs_repo.get_run(db_path, "run1")
    assert row["status"] == "succeeded"
    assert row["finished_at"] is not None


def test_mark_failed_records_error(tmp_path):
    db_path = _fresh_db(tmp_path)
    runs_repo.insert_run(db_path, "run1", "stoicism", "cli", ["youtube"])

    runs_repo.mark_failed(db_path, "run1", "boom")
    row = runs_repo.get_run(db_path, "run1")
    assert row["status"] == "failed"
    assert row["error_message"] == "boom"


def test_append_event_and_list_events_since(tmp_path):
    db_path = _fresh_db(tmp_path)
    runs_repo.insert_run(db_path, "run1", "stoicism", "cli", ["youtube"])

    runs_repo.append_event(db_path, "run1", "search", "found 5 videos")
    runs_repo.append_event(db_path, "run1", "download", "downloaded")

    all_events = runs_repo.list_events_since(db_path, "run1", since_id=0)
    assert [e["stage"] for e in all_events] == ["search", "download"]

    later_events = runs_repo.list_events_since(db_path, "run1", since_id=all_events[0]["id"])
    assert [e["stage"] for e in later_events] == ["download"]

    assert runs_repo.get_run(db_path, "run1")["current_stage"] == "download"


def test_list_recent_orders_newest_first(tmp_path):
    db_path = _fresh_db(tmp_path)
    runs_repo.insert_run(db_path, "run1", "topic1", "cli", ["youtube"])
    runs_repo.insert_run(db_path, "run2", "topic2", "cli", ["youtube"])

    recent = runs_repo.list_recent(db_path)
    assert [r["run_id"] for r in recent] == ["run2", "run1"]


def test_sweep_stale_running_marks_pending_and_running_as_failed(tmp_path):
    db_path = _fresh_db(tmp_path)
    runs_repo.insert_run(db_path, "run1", "topic1", "cli", ["youtube"])
    runs_repo.insert_run(db_path, "run2", "topic2", "cli", ["youtube"])
    runs_repo.mark_running(db_path, "run2")
    runs_repo.mark_succeeded(db_path, "run2")

    runs_repo.insert_run(db_path, "run3", "topic3", "cli", ["youtube"])
    runs_repo.mark_running(db_path, "run3")

    swept = runs_repo.sweep_stale_running(db_path)
    assert swept == 2

    assert runs_repo.get_run(db_path, "run1")["status"] == "failed"
    assert runs_repo.get_run(db_path, "run2")["status"] == "succeeded"
    assert runs_repo.get_run(db_path, "run3")["status"] == "failed"
