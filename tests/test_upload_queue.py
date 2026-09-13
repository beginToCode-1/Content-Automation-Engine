import json
from unittest.mock import MagicMock, patch

from content_engine.db import runs_repo, uploads_repo
from content_engine.models import PlatformUploadOutcome, UploadResult
from content_engine.webapp import upload_queue
from tests.test_pipeline_progress_callback import _fake_settings


def _seed_queued_run(pool, settings, run_id, platforms):
    runs_repo.insert_run(pool, run_id, "topic", "web", platforms)
    runs_repo.update_fields(
        pool,
        run_id,
        clip_path=str(settings.work_dir / "clip.mp4"),
        metadata_title="Title",
        metadata_description="Desc",
        metadata_hashtags=json.dumps(["a", "b"]),
        effective_privacy="private",
        scheduled_upload_at="2000-01-01T00:00:00.000000Z",
    )
    uploads_repo.insert_pending_uploads(pool, run_id, platforms)


def test_process_due_upload_success_marks_run_succeeded_and_clears_schedule(pg_pool, tmp_path):
    settings = _fake_settings(tmp_path)
    _seed_queued_run(pg_pool, settings, "run1", ["youtube"])
    run_row = runs_repo.get_run(pg_pool, "run1")

    outcome = PlatformUploadOutcome(
        platform="youtube",
        result=UploadResult(video_id="v1", url="https://youtube.com/shorts/v1", privacy_status="private"),
    )

    with patch("content_engine.webapp.upload_queue.upload_clip_to_platforms", return_value=[outcome]) as mock_upload:
        upload_queue.process_due_upload(settings, run_row)

    mock_upload.assert_called_once()
    assert mock_upload.call_args.kwargs["raise_if_all_failed"] is False

    updated = runs_repo.get_run(pg_pool, "run1")
    assert updated["status"] == "succeeded"
    assert updated["scheduled_upload_at"] is None

    uploads = uploads_repo.list_uploads_for_run(pg_pool, "run1")
    assert uploads[0]["status"] == "succeeded"
    assert uploads[0]["video_id"] == "v1"


def test_process_due_upload_all_failed_marks_run_failed(pg_pool, tmp_path):
    settings = _fake_settings(tmp_path)
    _seed_queued_run(pg_pool, settings, "run1", ["youtube"])
    run_row = runs_repo.get_run(pg_pool, "run1")

    outcome = PlatformUploadOutcome(platform="youtube", result=None, error="quota exceeded")

    with patch("content_engine.webapp.upload_queue.upload_clip_to_platforms", return_value=[outcome]):
        upload_queue.process_due_upload(settings, run_row)

    updated = runs_repo.get_run(pg_pool, "run1")
    assert updated["status"] == "failed"
    assert "quota exceeded" in updated["error_message"]

    uploads = uploads_repo.list_uploads_for_run(pg_pool, "run1")
    assert uploads[0]["status"] == "failed"


def test_process_due_upload_marks_uploading_before_calling_upload(pg_pool, tmp_path):
    settings = _fake_settings(tmp_path)
    _seed_queued_run(pg_pool, settings, "run1", ["youtube"])
    run_row = runs_repo.get_run(pg_pool, "run1")

    seen_status_during_call = {}

    def fake_upload(*args, **kwargs):
        rows = uploads_repo.list_uploads_for_run(pg_pool, "run1")
        seen_status_during_call["status"] = rows[0]["status"]
        return [PlatformUploadOutcome(platform="youtube", result=None, error="x")]

    with patch("content_engine.webapp.upload_queue.upload_clip_to_platforms", side_effect=fake_upload):
        upload_queue.process_due_upload(settings, run_row)

    assert seen_status_during_call["status"] == "uploading"


def test_process_due_upload_noop_when_nothing_pending(pg_pool, tmp_path):
    settings = _fake_settings(tmp_path)
    _seed_queued_run(pg_pool, settings, "run1", ["youtube"])
    uploads_repo.mark_uploading(pg_pool, "run1")  # simulate already-processed
    run_row = runs_repo.get_run(pg_pool, "run1")

    with patch("content_engine.webapp.upload_queue.upload_clip_to_platforms") as mock_upload:
        upload_queue.process_due_upload(settings, run_row)

    mock_upload.assert_not_called()
    updated = runs_repo.get_run(pg_pool, "run1")
    assert updated["scheduled_upload_at"] is None
