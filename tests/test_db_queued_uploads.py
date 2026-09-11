from datetime import datetime, timedelta

from content_engine.db.connection import init_db
from content_engine.db import batches_repo, runs_repo, uploads_repo
from content_engine.models import PlatformUploadOutcome, UploadResult


def _fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _seed_run(db_path, run_id, batch_id=None):
    runs_repo.insert_run(db_path, run_id, "topic", "web", ["youtube"])
    if batch_id:
        batches_repo.insert_batch(db_path, batch_id, "topic", ["youtube"], 1, 1, 60)
        runs_repo.update_fields(db_path, run_id, batch_id=batch_id, video_rank=1, clip_rank=1)


def test_list_due_queued_uploads_finds_past_due_run_with_pending_upload(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    uploads_repo.insert_pending_uploads(db_path, "run1", ["youtube"])
    runs_repo.update_fields(db_path, "run1", scheduled_upload_at="2000-01-01T00:00:00.000000Z")

    due = runs_repo.list_due_queued_uploads(db_path, now=datetime(2026, 1, 1))
    assert len(due) == 1
    assert due[0]["run_id"] == "run1"


def test_list_due_queued_uploads_ignores_future_scheduled_time(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    uploads_repo.insert_pending_uploads(db_path, "run1", ["youtube"])
    runs_repo.update_fields(db_path, "run1", scheduled_upload_at="2999-01-01T00:00:00.000000Z")

    due = runs_repo.list_due_queued_uploads(db_path, now=datetime(2026, 1, 1))
    assert due == []


def test_list_due_queued_uploads_ignores_run_with_no_pending_upload_rows(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    runs_repo.update_fields(db_path, "run1", scheduled_upload_at="2000-01-01T00:00:00.000000Z")
    # no insert_pending_uploads call - nothing to find

    due = runs_repo.list_due_queued_uploads(db_path, now=datetime(2026, 1, 1))
    assert due == []


def test_clear_scheduled_upload_removes_the_timestamp(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    runs_repo.update_fields(db_path, "run1", scheduled_upload_at="2000-01-01T00:00:00.000000Z")

    runs_repo.clear_scheduled_upload(db_path, "run1")

    assert runs_repo.get_run(db_path, "run1")["scheduled_upload_at"] is None


def test_list_runs_for_batch_orders_by_video_and_clip_rank(tmp_path):
    db_path = _fresh_db(tmp_path)
    batches_repo.insert_batch(db_path, "batch1", "topic", ["youtube"], 2, 2, 60)
    for run_id, video_rank, clip_rank in [("r3", 2, 1), ("r1", 1, 1), ("r2", 1, 2)]:
        runs_repo.insert_run(db_path, run_id, "topic", "web", ["youtube"])
        runs_repo.update_fields(db_path, run_id, batch_id="batch1", video_rank=video_rank, clip_rank=clip_rank)

    ordered = runs_repo.list_runs_for_batch(db_path, "batch1")
    assert [r["run_id"] for r in ordered] == ["r1", "r2", "r3"]


def test_insert_pending_uploads_then_mark_uploading(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    uploads_repo.insert_pending_uploads(db_path, "run1", ["youtube", "tiktok"])

    uploads = uploads_repo.list_uploads_for_run(db_path, "run1")
    assert {u["platform"]: u["status"] for u in uploads} == {"youtube": "pending", "tiktok": "pending"}

    uploads_repo.mark_uploading(db_path, "run1")
    uploads = uploads_repo.list_uploads_for_run(db_path, "run1")
    assert all(u["status"] == "uploading" for u in uploads)


def test_skip_pending_uploads_marks_pending_rows_skipped(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    uploads_repo.insert_pending_uploads(db_path, "run1", ["youtube"])

    uploads_repo.skip_pending_uploads(db_path, "run1")

    uploads = uploads_repo.list_uploads_for_run(db_path, "run1")
    assert uploads[0]["status"] == "skipped"


def test_sweep_stale_uploading_marks_failed(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    uploads_repo.insert_pending_uploads(db_path, "run1", ["youtube"])
    uploads_repo.mark_uploading(db_path, "run1")

    swept = uploads_repo.sweep_stale_uploading(db_path)

    assert swept == 1
    uploads = uploads_repo.list_uploads_for_run(db_path, "run1")
    assert uploads[0]["status"] == "failed"
    assert uploads[0]["error_message"] == "Interrupted by dashboard restart"


def test_record_upload_outcomes_writes_success_and_failure(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_run(db_path, "run1")
    outcomes = [
        PlatformUploadOutcome(
            platform="youtube",
            result=UploadResult(video_id="v1", url="https://youtube.com/shorts/v1", privacy_status="private"),
        ),
        PlatformUploadOutcome(platform="tiktok", result=None, error="not authorized"),
    ]

    uploads_repo.record_upload_outcomes(db_path, "run1", outcomes)

    uploads = {u["platform"]: u for u in uploads_repo.list_uploads_for_run(db_path, "run1")}
    assert uploads["youtube"]["status"] == "succeeded"
    assert uploads["youtube"]["video_id"] == "v1"
    assert uploads["tiktok"]["status"] == "failed"
    assert uploads["tiktok"]["error_message"] == "not authorized"
