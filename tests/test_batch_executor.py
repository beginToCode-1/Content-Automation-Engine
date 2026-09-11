from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from content_engine.db.connection import init_db
from content_engine.db import batches_repo, runs_repo, uploads_repo
from content_engine.models import ClipMetadata, GeneratedClip, TranscriptLine, TranscriptSegment, VideoCandidate
from content_engine.webapp import batch_executor
from tests.test_pipeline_progress_callback import _fake_settings


def _fake_clip(run_id, video_rank, clip_rank, work_dir):
    return GeneratedClip(
        run_id=run_id,
        source_video=VideoCandidate(
            video_id="v1", title="video", description="", channel="c", published_at="", duration_s=200
        ),
        segment=TranscriptSegment(
            start_s=0, end_s=30, text="t", lines=[TranscriptLine("t", 0, 30)], score=0.9
        ),
        clip_path=work_dir / "clip.mp4",
        metadata=ClipMetadata(title="Title", description="Desc", hashtags=["a"]),
        work_dir=work_dir,
        video_rank=video_rank,
        clip_rank=clip_rank,
    )


def test_execute_batch_staggers_uploads_exactly(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)

    fixed_now = datetime(2026, 1, 1, 12, 0, 0)
    clips = [_fake_clip(f"run{i}", 1, i + 1, tmp_path) for i in range(3)]

    def fake_generate(topic, settings_arg, batch_id, videos_count, clips_per_video, on_progress=None, on_clip_ready=None):
        for i, clip in enumerate(clips):
            on_clip_ready(clip, clip.video_rank, clip.clip_rank)
        return clips

    batches_repo.insert_batch(settings.db_path, "batch1", "stoic philosophy", ["youtube"], 1, 3, 60)

    with patch("content_engine.webapp.batch_executor.generate_clips_for_topic", side_effect=fake_generate), patch(
        "content_engine.webapp.batch_executor.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        batch_executor._execute_batch(
            settings, "batch1", "stoic philosophy", ["youtube"], 1, 3, stagger_gap_minutes=60, privacy_override=None
        )

    for i, clip in enumerate(clips):
        row = runs_repo.get_run(settings.db_path, clip.run_id)
        expected = (fixed_now + timedelta(minutes=60 * (i + 1))).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        assert row["scheduled_upload_at"] == expected
        assert row["batch_id"] == "batch1"
        assert row["status"] == "succeeded"

        uploads = uploads_repo.list_uploads_for_run(settings.db_path, clip.run_id)
        assert len(uploads) == 1
        assert uploads[0]["status"] == "pending"

    batch = batches_repo.get_batch(settings.db_path, "batch1")
    assert batch["status"] == "succeeded"


def test_execute_batch_marks_failed_on_generation_error(tmp_path):
    settings = _fake_settings(tmp_path)
    init_db(settings.db_path)

    from content_engine.errors import SearchFailedError

    batches_repo.insert_batch(settings.db_path, "batch2", "topic", ["youtube"], 1, 1, 60)

    with patch(
        "content_engine.webapp.batch_executor.generate_clips_for_topic",
        side_effect=SearchFailedError("no results"),
    ):
        batch_executor._execute_batch(
            settings, "batch2", "topic", ["youtube"], 1, 1, stagger_gap_minutes=60, privacy_override=None
        )

    batch = batches_repo.get_batch(settings.db_path, "batch2")
    assert batch["status"] == "failed"
    assert batch["error_message"] == "no results"
