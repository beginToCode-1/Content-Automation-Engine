import threading
import time
from unittest.mock import patch

from content_engine.db import runs_repo
from content_engine.webapp import executor
from tests.test_pipeline_progress_callback import _fake_settings, _patch_stages


def test_cancel_run_mid_flight_marks_run_cancelled(pg_pool, tmp_path):
    settings = _fake_settings(tmp_path)

    download_started = threading.Event()
    release_download = threading.Event()

    def blocking_download(video_id, run_dir):
        download_started.set()
        release_download.wait(timeout=5)
        from content_engine.models import DownloadResult

        return DownloadResult(
            video_path=tmp_path / "source.mp4", info_json_path=tmp_path / "i.json", duration_s=120.0
        )

    executor.init_executor(2)
    try:
        with _patch_stages(tmp_path), patch("content_engine.pipeline.download_video", side_effect=blocking_download):
            run_id = executor.submit_run(
                settings, topic="stoic philosophy", trigger_source="web", target_platforms=["youtube"], dry_run=True
            )

            assert download_started.wait(timeout=5), "pipeline never reached the download stage"

            cancelled = executor.cancel_run(settings, run_id)
            assert cancelled is True

            release_download.set()

            deadline = time.monotonic() + 5
            row = runs_repo.get_run(pg_pool, run_id)
            while row["status"] not in ("succeeded", "failed", "cancelled") and time.monotonic() < deadline:
                time.sleep(0.05)
                row = runs_repo.get_run(pg_pool, run_id)

        assert row["status"] == "cancelled"
        assert row["error_message"] == "Cancelled by user"
    finally:
        executor.shutdown_executor()


def test_cancel_run_before_start_still_works(pg_pool, tmp_path):
    """Unchanged pre-existing behavior: a run that hasn't started executing
    yet is cancelled outright via future.cancel(), no cooperative check needed."""
    settings = _fake_settings(tmp_path)

    # A single-worker executor whose one slot is occupied by a run that blocks
    # forever (until released) guarantees the second submitted run is still
    # queued (never started) when we call cancel_run on it.
    block_first = threading.Event()
    release_first = threading.Event()

    def blocking_download(video_id, run_dir):
        block_first.set()
        release_first.wait(timeout=5)
        from content_engine.models import DownloadResult

        return DownloadResult(
            video_path=tmp_path / "source.mp4", info_json_path=tmp_path / "i.json", duration_s=120.0
        )

    executor.init_executor(1)
    try:
        with _patch_stages(tmp_path), patch("content_engine.pipeline.download_video", side_effect=blocking_download):
            first_run_id = executor.submit_run(
                settings, topic="stoic philosophy", trigger_source="web", target_platforms=["youtube"], dry_run=True
            )
            assert block_first.wait(timeout=5)

            second_run_id = executor.submit_run(
                settings, topic="stoic virtue", trigger_source="web", target_platforms=["youtube"], dry_run=True
            )

            cancelled = executor.cancel_run(settings, second_run_id)
            assert cancelled is True

            row = runs_repo.get_run(pg_pool, second_run_id)
            assert row["status"] == "failed"
            assert "before it started" in row["error_message"]

            release_first.set()
    finally:
        executor.shutdown_executor()
