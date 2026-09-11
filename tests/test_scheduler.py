import asyncio
from unittest.mock import patch

from content_engine.db.connection import init_db
from content_engine.db import runs_repo, schedules_repo, uploads_repo
from content_engine.webapp import scheduler
from tests.test_pipeline_progress_callback import _fake_settings


def _fake_submit_run(run_id_to_return):
    def _submit(settings, **kwargs):
        runs_repo.insert_run(
            settings.db_path, run_id_to_return, kwargs["topic"], kwargs["trigger_source"], kwargs["target_platforms"]
        )
        return run_id_to_return

    return _submit


def test_poll_once_always_forces_private_regardless_of_entry(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)
    schedules_repo.insert_schedule(
        settings.db_path, "topic-x", "once", ["youtube"], scheduled_time="2000-01-01T00:00:00.000000Z"
    )

    with patch(
        "content_engine.webapp.scheduler.executor.submit_run", side_effect=_fake_submit_run("run123")
    ) as mock_submit:
        asyncio.run(scheduler._poll_once(settings))

    assert mock_submit.call_count == 1
    _, kwargs = mock_submit.call_args
    assert kwargs["force_private"] is True
    assert kwargs["trigger_source"] == "scheduled"


def test_poll_once_marks_once_schedule_completed(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)
    schedule_id = schedules_repo.insert_schedule(
        settings.db_path, "topic-y", "once", ["youtube"], scheduled_time="2000-01-01T00:00:00.000000Z"
    )

    with patch(
        "content_engine.webapp.scheduler.executor.submit_run", side_effect=_fake_submit_run("run456")
    ):
        asyncio.run(scheduler._poll_once(settings))

    active = schedules_repo.list_active(settings.db_path)
    entry = next(e for e in active if e["id"] == schedule_id)
    assert entry["status"] == "completed"
    assert entry["last_run_id"] == "run456"


def test_poll_once_no_due_entries_does_not_submit(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)
    schedules_repo.insert_schedule(
        settings.db_path, "topic-z", "once", ["youtube"], scheduled_time="2999-01-01T00:00:00.000000Z"
    )

    with patch("content_engine.webapp.scheduler.executor.submit_run") as mock_submit:
        asyncio.run(scheduler._poll_once(settings))

    mock_submit.assert_not_called()


def test_poll_once_processes_due_queued_uploads(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)
    runs_repo.insert_run(settings.db_path, "run1", "topic", "web", ["youtube"])
    uploads_repo.insert_pending_uploads(settings.db_path, "run1", ["youtube"])
    runs_repo.update_fields(settings.db_path, "run1", scheduled_upload_at="2000-01-01T00:00:00.000000Z")

    with patch("content_engine.webapp.scheduler.executor.submit_run") as mock_submit_run, patch(
        "content_engine.webapp.scheduler.upload_queue.process_due_upload"
    ) as mock_process:
        asyncio.run(scheduler._poll_once(settings))

    mock_submit_run.assert_not_called()
    mock_process.assert_called_once()
    assert mock_process.call_args.args[1]["run_id"] == "run1"


def test_poll_once_ignores_future_scheduled_uploads(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)
    runs_repo.insert_run(settings.db_path, "run1", "topic", "web", ["youtube"])
    uploads_repo.insert_pending_uploads(settings.db_path, "run1", ["youtube"])
    runs_repo.update_fields(settings.db_path, "run1", scheduled_upload_at="2999-01-01T00:00:00.000000Z")

    with patch("content_engine.webapp.scheduler.upload_queue.process_due_upload") as mock_process:
        asyncio.run(scheduler._poll_once(settings))

    mock_process.assert_not_called()
