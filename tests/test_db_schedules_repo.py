from datetime import datetime

from content_engine.db.connection import init_db
from content_engine.db import runs_repo, schedules_repo


def _fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_once_schedule_due_when_scheduled_time_has_passed(tmp_path):
    db_path = _fresh_db(tmp_path)
    schedules_repo.insert_schedule(
        db_path, "topic-a", "once", ["youtube"], scheduled_time="2026-01-01T00:00:00.000000Z"
    )

    due = schedules_repo.find_due(db_path, now=datetime(2026, 1, 2, 0, 0, 0))
    assert len(due) == 1
    assert due[0]["topic"] == "topic-a"


def test_once_schedule_not_due_before_scheduled_time(tmp_path):
    db_path = _fresh_db(tmp_path)
    schedules_repo.insert_schedule(
        db_path, "topic-a", "once", ["youtube"], scheduled_time="2026-06-01T00:00:00.000000Z"
    )

    due = schedules_repo.find_due(db_path, now=datetime(2026, 1, 2, 0, 0, 0))
    assert due == []


def test_daily_schedule_due_once_per_day(tmp_path):
    db_path = _fresh_db(tmp_path)
    schedule_id = schedules_repo.insert_schedule(
        db_path, "topic-b", "daily", ["youtube"], daily_time="09:00"
    )

    now = datetime(2026, 1, 1, 9, 30, 0)
    due = schedules_repo.find_due(db_path, now=now)
    assert len(due) == 1

    runs_repo.insert_run(db_path, "run1", "topic-b", "scheduled", ["youtube"])
    schedules_repo.mark_triggered(db_path, schedule_id, "run1", now)

    due_again_same_day = schedules_repo.find_due(db_path, now=datetime(2026, 1, 1, 10, 0, 0))
    assert due_again_same_day == []

    due_next_day = schedules_repo.find_due(db_path, now=datetime(2026, 1, 2, 9, 30, 0))
    assert len(due_next_day) == 1


def test_cancelled_schedule_never_due(tmp_path):
    db_path = _fresh_db(tmp_path)
    schedule_id = schedules_repo.insert_schedule(
        db_path, "topic-c", "once", ["youtube"], scheduled_time="2026-01-01T00:00:00.000000Z"
    )
    schedules_repo.cancel(db_path, schedule_id)

    due = schedules_repo.find_due(db_path, now=datetime(2026, 6, 1, 0, 0, 0))
    assert due == []


def test_completed_once_schedule_never_due_again(tmp_path):
    db_path = _fresh_db(tmp_path)
    schedule_id = schedules_repo.insert_schedule(
        db_path, "topic-d", "once", ["youtube"], scheduled_time="2026-01-01T00:00:00.000000Z"
    )
    schedules_repo.mark_completed(db_path, schedule_id)

    due = schedules_repo.find_due(db_path, now=datetime(2026, 6, 1, 0, 0, 0))
    assert due == []
