import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from content_engine.config import Settings
from content_engine.db import connection, runs_repo, uploads_repo
from content_engine.errors import PipelineError
from content_engine.pipeline import run_pipeline

logger = logging.getLogger("content_engine.webapp.executor")

_executor: ThreadPoolExecutor | None = None
_futures: dict[str, object] = {}


def init_executor(max_workers: int) -> None:
    global _executor
    _executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pipeline-run")
    _futures.clear()


def shutdown_executor() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
    _futures.clear()


def run_in_background(func, *args) -> None:
    """Submits an arbitrary callable to the same worker pool used for single-clip
    runs, so batch generation and self-upload publishing share the one
    dashboard_max_workers concurrency limit rather than spinning up a second pool."""
    if _executor is None:
        raise RuntimeError("executor not initialized - call init_executor() first")
    _executor.submit(func, *args)


def cancel_run(settings: Settings, run_id: str) -> bool:
    """Best-effort cancel: only succeeds if the run hasn't started executing yet
    (a ThreadPoolExecutor Future can't be cancelled once it's running)."""
    future = _futures.get(run_id)
    if future is None:
        return False
    cancelled = future.cancel()
    if cancelled:
        runs_repo.mark_failed(connection.get_pool(), run_id, "Cancelled by user before it started")
    return cancelled


def submit_run(
    settings: Settings,
    topic: str,
    trigger_source: str,
    target_platforms: list[str],
    dry_run: bool = False,
    privacy_override: str | None = None,
    schedule_id: int | None = None,
    force_private: bool = False,
    user_id: str | None = None,
    youtube_account_id: str | None = None,
) -> str:
    if _executor is None:
        raise RuntimeError("executor not initialized - call init_executor() first")

    run_id = uuid.uuid4().hex[:10]
    runs_repo.insert_run(
        connection.get_pool(),
        run_id,
        topic,
        trigger_source,
        target_platforms,
        dry_run=dry_run,
        requested_privacy=privacy_override,
        schedule_id=schedule_id,
        user_id=user_id,
        youtube_account_id=youtube_account_id,
    )
    future = _executor.submit(
        _execute,
        settings,
        run_id,
        topic,
        dry_run,
        privacy_override,
        target_platforms,
        force_private,
        youtube_account_id,
    )
    _futures[run_id] = future
    return run_id


def _execute(
    settings: Settings,
    run_id: str,
    topic: str,
    dry_run: bool,
    privacy_override: str | None,
    target_platforms: list[str],
    force_private: bool,
    youtube_account_id: str | None = None,
) -> None:
    try:
        _run_execute(
            settings, run_id, topic, dry_run, privacy_override, target_platforms, force_private, youtube_account_id
        )
    finally:
        # Completed runs' Futures serve no purpose after this point (cancel_run
        # can't cancel a finished run anyway) - without this, a long-lived
        # server process accumulates one dict entry per run forever.
        _futures.pop(run_id, None)


def _run_execute(
    settings: Settings,
    run_id: str,
    topic: str,
    dry_run: bool,
    privacy_override: str | None,
    target_platforms: list[str],
    force_private: bool,
    youtube_account_id: str | None = None,
) -> None:
    runs_repo.mark_running(connection.get_pool(), run_id)

    def on_progress(stage: str, message: str) -> None:
        runs_repo.append_event(connection.get_pool(), run_id, stage, message)

    try:
        result = run_pipeline(
            topic,
            settings,
            dry_run=dry_run,
            privacy_override=privacy_override,
            target_platforms=target_platforms,
            force_private=force_private,
            run_id=run_id,
            on_progress=on_progress,
            youtube_account_id=youtube_account_id,
        )
    except PipelineError as e:
        runs_repo.mark_failed(connection.get_pool(), run_id, str(e))
        return
    except Exception as e:
        logger.exception("Unexpected error in run %s", run_id)
        runs_repo.mark_failed(connection.get_pool(), run_id, f"Unexpected error: {e}")
        return

    runs_repo.update_fields(
        connection.get_pool(),
        run_id,
        source_video_id=result.source_video.video_id,
        source_video_title=result.source_video.title,
        source_video_url=f"https://youtube.com/watch?v={result.source_video.video_id}",
        segment_start_s=result.segment.start_s,
        segment_end_s=result.segment.end_s,
        segment_score=result.segment.score,
        clip_path=str(result.clip_path),
        metadata_title=result.metadata.title,
        metadata_description=result.metadata.description,
        metadata_hashtags=json.dumps(result.metadata.hashtags),
        work_dir=str(result.work_dir),
        effective_privacy="private" if force_private else (privacy_override or settings.upload_privacy_status),
    )

    uploads_repo.record_upload_outcomes(connection.get_pool(), run_id, result.uploads)
    runs_repo.mark_succeeded(connection.get_pool(), run_id)
