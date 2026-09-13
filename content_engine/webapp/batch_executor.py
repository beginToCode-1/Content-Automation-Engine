import json
import logging
import uuid
from datetime import datetime, timedelta

from content_engine.config import Settings
from content_engine.db import batches_repo, connection, runs_repo, uploads_repo
from content_engine.errors import PipelineError
from content_engine.models import GeneratedClip
from content_engine.pipeline import generate_clips_for_topic
from content_engine.webapp import executor

logger = logging.getLogger("content_engine.webapp.batch_executor")


def submit_batch(
    settings: Settings,
    topic: str,
    target_platforms: list[str],
    videos_count: int,
    clips_per_video: int,
    stagger_gap_minutes: int,
    privacy_override: str | None = None,
    user_id: str | None = None,
    youtube_account_id: str | None = None,
) -> str:
    batch_id = uuid.uuid4().hex[:10]
    batches_repo.insert_batch(
        connection.get_pool(),
        batch_id,
        topic,
        target_platforms,
        videos_count,
        clips_per_video,
        stagger_gap_minutes,
        requested_privacy=privacy_override,
        user_id=user_id,
        youtube_account_id=youtube_account_id,
    )
    executor.run_in_background(
        _execute_batch,
        settings,
        batch_id,
        topic,
        target_platforms,
        videos_count,
        clips_per_video,
        stagger_gap_minutes,
        privacy_override,
        user_id,
        youtube_account_id,
    )
    return batch_id


def _execute_batch(
    settings: Settings,
    batch_id: str,
    topic: str,
    target_platforms: list[str],
    videos_count: int,
    clips_per_video: int,
    stagger_gap_minutes: int,
    privacy_override: str | None,
    user_id: str | None = None,
    youtube_account_id: str | None = None,
) -> None:
    effective_privacy = privacy_override or settings.upload_privacy_status
    clip_index = 0

    def on_progress(stage: str, message: str) -> None:
        logger.info("[batch %s] %s: %s", batch_id, stage, message)

    def on_clip_ready(clip: GeneratedClip, video_rank: int, clip_rank: int) -> None:
        nonlocal clip_index
        clip_index += 1
        scheduled_upload_at = (
            datetime.now() + timedelta(minutes=stagger_gap_minutes * clip_index)
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        runs_repo.insert_run(
            connection.get_pool(),
            clip.run_id,
            topic,
            trigger_source="web",
            target_platforms=target_platforms,
            dry_run=False,
            requested_privacy=privacy_override,
            work_dir=str(clip.work_dir),
            user_id=user_id,
            youtube_account_id=youtube_account_id,
        )
        runs_repo.mark_running(connection.get_pool(), clip.run_id)
        runs_repo.update_fields(
            connection.get_pool(),
            clip.run_id,
            batch_id=batch_id,
            video_rank=video_rank,
            clip_rank=clip_rank,
            source_video_id=clip.source_video.video_id,
            source_video_title=clip.source_video.title,
            source_video_url=f"https://youtube.com/watch?v={clip.source_video.video_id}",
            segment_start_s=clip.segment.start_s,
            segment_end_s=clip.segment.end_s,
            segment_score=clip.segment.score,
            clip_path=str(clip.clip_path),
            metadata_title=clip.metadata.title,
            metadata_description=clip.metadata.description,
            metadata_hashtags=json.dumps(clip.metadata.hashtags),
            effective_privacy=effective_privacy,
            scheduled_upload_at=scheduled_upload_at,
        )
        uploads_repo.insert_pending_uploads(connection.get_pool(), clip.run_id, target_platforms)
        runs_repo.mark_succeeded(connection.get_pool(), clip.run_id)

    try:
        generate_clips_for_topic(
            topic,
            settings,
            batch_id,
            videos_count=videos_count,
            clips_per_video=clips_per_video,
            on_progress=on_progress,
            on_clip_ready=on_clip_ready,
            youtube_account_id=youtube_account_id,
        )
    except PipelineError as e:
        logger.error("Batch %s generation failed: %s", batch_id, e)
        # A clip already generated (and queued via on_clip_ready) before this
        # error is real, finished work - don't mark the whole batch "failed"
        # out from under clips that already succeeded and are pending upload.
        if clip_index > 0:
            batches_repo.mark_batch_finished(
                connection.get_pool(), batch_id, "succeeded",
                error_message=f"Stopped early after {clip_index} clip(s): {e}",
            )
        else:
            batches_repo.mark_batch_finished(connection.get_pool(), batch_id, "failed", error_message=str(e))
        return
    except Exception as e:
        logger.exception("Unexpected error generating batch %s", batch_id)
        if clip_index > 0:
            batches_repo.mark_batch_finished(
                connection.get_pool(), batch_id, "succeeded",
                error_message=f"Stopped early after {clip_index} clip(s): Unexpected error: {e}",
            )
        else:
            batches_repo.mark_batch_finished(
                connection.get_pool(), batch_id, "failed", error_message=f"Unexpected error: {e}"
            )
        return

    if clip_index == 0:
        batches_repo.mark_batch_finished(connection.get_pool(), batch_id, "failed", error_message="No clips were generated")
    else:
        batches_repo.mark_batch_finished(connection.get_pool(), batch_id, "succeeded")
