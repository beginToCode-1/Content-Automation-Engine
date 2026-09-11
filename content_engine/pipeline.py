import dataclasses
import json
import logging
import uuid
from pathlib import Path
from typing import Callable

from content_engine.auth.google_oauth import ALL_SCOPES, get_youtube_client
from content_engine.config import Settings
from content_engine.download.yt_dlp_downloader import download_video
from content_engine.errors import PipelineError, UploadFailedError
from content_engine.metadata.generate_metadata import generate_metadata
from content_engine.models import ClipMetadata, GeneratedClip, PipelineResult, PlatformUploadOutcome
from content_engine.notifications.dispatch import notify_upload_outcome
from content_engine.render.clip_builder import build_clip
from content_engine.search.youtube_search import build_search_client, search_videos, select_best, select_top
from content_engine.transcript.fetch import get_transcript
from content_engine.transcript.select_segment import select_best_segment, select_top_segments
from content_engine.uploaders.instagram_uploader import InstagramUploader
from content_engine.uploaders.tiktok_uploader import TikTokUploader
from content_engine.uploaders.youtube_uploader import YouTubeUploader

ProgressCallback = Callable[[str, str], None]


def _setup_logger(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"content_engine.run.{run_dir.name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def _notify(on_progress: ProgressCallback | None, logger: logging.Logger, stage: str, message: str) -> None:
    if on_progress is None:
        return
    try:
        on_progress(stage, message)
    except Exception:
        logger.exception("on_progress callback raised for stage=%s (ignored)", stage)


def _build_uploader(platform: str, oauth_client, settings: Settings):
    if platform == "youtube":
        return YouTubeUploader(oauth_client)
    if platform == "instagram":
        return InstagramUploader(settings)
    if platform == "tiktok":
        return TikTokUploader(settings)
    raise UploadFailedError(f"Unknown upload platform: {platform!r}")


def upload_clip_to_platforms(
    clip_path: Path,
    metadata: ClipMetadata,
    platforms: list[str],
    settings: Settings,
    effective_privacy: str,
    topic: str,
    run_id: str,
    oauth_client=None,
    on_progress: ProgressCallback | None = None,
    notification_label: str | None = None,
    logger: logging.Logger | None = None,
    raise_if_all_failed: bool = True,
) -> list[PlatformUploadOutcome]:
    """Uploads one finished clip to each requested platform. Extracted from
    run_pipeline() so both the immediate-upload path and any deferred/queued
    upload path (batch runs, self-upload publish) share identical behavior:
    same per-platform error handling, same notification firing point.

    `raise_if_all_failed` defaults to True to preserve run_pipeline()'s exact
    existing behavior (raise UploadFailedError if every platform failed).
    Callers that need the outcomes list even when everything failed - so they
    can record per-platform results themselves, e.g. a queued upload whose
    run_uploads rows already exist and must be resolved to a terminal state
    either way - should pass False and inspect the returned outcomes instead.
    """
    logger = logger or logging.getLogger("content_engine.pipeline")
    label = notification_label or topic

    if "youtube" in platforms and oauth_client is None:
        oauth_client = get_youtube_client(ALL_SCOPES, settings)

    upload_outcomes: list[PlatformUploadOutcome] = []
    for platform in platforms:
        try:
            uploader = _build_uploader(platform, oauth_client, settings)
            result = uploader.upload(clip_path, metadata, effective_privacy)
            outcome = PlatformUploadOutcome(platform=platform, result=result)
            text = f"Uploaded to {platform}: {result.url} (privacy={result.privacy_status})"
            logger.info(text)
            _notify(on_progress, logger, f"upload_{platform}", text)
        except (UploadFailedError, NotImplementedError) as e:
            outcome = PlatformUploadOutcome(platform=platform, result=None, error=str(e))
            text = f"Upload to {platform} failed: {e}"
            logger.error(text)
            _notify(on_progress, logger, f"upload_{platform}", text)

        upload_outcomes.append(outcome)
        try:
            notify_upload_outcome(settings, topic, label, platform, outcome, run_id)
        except Exception:
            logger.exception("notify_upload_outcome raised (ignored)")

    if raise_if_all_failed and platforms and not any(o.result for o in upload_outcomes):
        raise UploadFailedError(
            "All requested platform uploads failed: "
            + "; ".join(f"{o.platform}: {o.error}" for o in upload_outcomes)
        )

    return upload_outcomes


def run_pipeline(
    topic: str,
    settings: Settings,
    dry_run: bool = False,
    privacy_override: str | None = None,
    target_platforms: list[str] | None = None,
    force_private: bool = False,
    run_id: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    run_id = run_id or uuid.uuid4().hex[:10]
    platforms = target_platforms or ["youtube"]
    run_dir = settings.work_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = _setup_logger(run_dir)
    logger.info("Starting run %s for topic: %s", run_id, topic)

    def notify(stage: str, message: str) -> None:
        _notify(on_progress, logger, stage, message)

    try:
        oauth_client = None
        if not settings.youtube_api_key:
            oauth_client = get_youtube_client(ALL_SCOPES, settings)
        search_client = build_search_client(settings.youtube_api_key, oauth_client)

        candidates = search_videos(topic, client=search_client)
        text = f"Found {len(candidates)} candidate videos"
        logger.info(text)
        notify("search", text)

        best_video = select_best(candidates, topic)
        text = f"Selected video {best_video.video_id}: {best_video.title}"
        logger.info(text)
        notify("search", text)

        download_result = download_video(best_video.video_id, run_dir)
        text = f"Downloaded video ({download_result.duration_s:.1f}s) to {download_result.video_path}"
        logger.info(text)
        notify("download", text)

        transcript = get_transcript(best_video.video_id)
        text = f"Fetched transcript with {len(transcript)} lines"
        logger.info(text)
        notify("transcript", text)

        segment = select_best_segment(transcript, topic)
        text = f"Selected segment {segment.start_s:.1f}-{segment.end_s:.1f}s (score={segment.score:.3f})"
        logger.info(text)
        notify("segment", text)

        clip_path = build_clip(download_result.video_path, segment, run_dir, title_overlay=topic)
        text = f"Built clip at {clip_path}"
        logger.info(text)
        notify("render", text)

        metadata = generate_metadata(topic, segment.text, settings.gemini_model, settings.gemini_api_key)
        (run_dir / "metadata.json").write_text(
            json.dumps(dataclasses.asdict(metadata), indent=2), encoding="utf-8"
        )
        text = f"Generated metadata: {metadata.title}"
        logger.info(text)
        notify("metadata", text)

        upload_outcomes: list[PlatformUploadOutcome] = []
        youtube_upload_result = None

        if dry_run:
            logger.info("Dry run: skipping upload")
            notify("upload", "Dry run: skipping upload")
        else:
            effective_privacy = "private" if force_private else (privacy_override or settings.upload_privacy_status)
            if force_private:
                logger.warning("Forced run: privacy forced to private regardless of any override")

            upload_outcomes = upload_clip_to_platforms(
                clip_path,
                metadata,
                platforms,
                settings,
                effective_privacy,
                topic,
                run_id,
                oauth_client=oauth_client,
                on_progress=on_progress,
                logger=logger,
            )
            for outcome in upload_outcomes:
                if outcome.platform == "youtube":
                    youtube_upload_result = outcome.result

        return PipelineResult(
            run_id=run_id,
            topic=topic,
            source_video=best_video,
            segment=segment,
            clip_path=clip_path,
            metadata=metadata,
            upload=youtube_upload_result,
            work_dir=run_dir,
            uploads=upload_outcomes,
        )
    except PipelineError as e:
        logger.error("Run failed: %s", e)
        raise


def generate_clips_for_topic(
    topic: str,
    settings: Settings,
    batch_id: str,
    videos_count: int = 2,
    clips_per_video: int = 3,
    on_progress: ProgressCallback | None = None,
    on_clip_ready: Callable[[GeneratedClip, int, int], None] | None = None,
) -> list[GeneratedClip]:
    """Generation-only counterpart to run_pipeline() for batch runs: searches once,
    selects up to `videos_count` different source videos, and for each video
    extracts up to `clips_per_video` non-overlapping clips. Never uploads -
    callers (the batch executor) are responsible for queuing/uploading each
    finished GeneratedClip separately. `on_clip_ready` fires as each clip finishes
    so the caller can persist incrementally rather than waiting for the whole batch.
    """
    logger = logging.getLogger(f"content_engine.batch.{batch_id}")

    def notify(stage: str, message: str) -> None:
        _notify(on_progress, logger, stage, message)

    oauth_client = None
    if not settings.youtube_api_key:
        oauth_client = get_youtube_client(ALL_SCOPES, settings)
    search_client = build_search_client(settings.youtube_api_key, oauth_client)

    candidates = search_videos(topic, client=search_client)
    text = f"Found {len(candidates)} candidate videos"
    logger.info(text)
    notify("search", text)

    videos = select_top(candidates, topic, count=videos_count)
    text = f"Selected {len(videos)} source video(s) for this batch"
    logger.info(text)
    notify("search", text)

    generated: list[GeneratedClip] = []
    for video_rank, video in enumerate(videos, start=1):
        video_work_dir = settings.work_dir / batch_id / f"video{video_rank}_source"
        video_work_dir.mkdir(parents=True, exist_ok=True)

        download_result = download_video(video.video_id, video_work_dir)
        text = f"Downloaded video {video_rank}/{len(videos)} ({download_result.duration_s:.1f}s): {video.title}"
        logger.info(text)
        notify("download", text)

        transcript = get_transcript(video.video_id)
        segments = select_top_segments(transcript, topic, count=clips_per_video)
        text = f"Selected {len(segments)} segment(s) from video {video_rank}"
        logger.info(text)
        notify("segment", text)

        for clip_rank, segment in enumerate(segments, start=1):
            clip_run_id = uuid.uuid4().hex[:10]
            clip_work_dir = settings.work_dir / clip_run_id
            clip_work_dir.mkdir(parents=True, exist_ok=True)

            clip_path = build_clip(download_result.video_path, segment, clip_work_dir, title_overlay=topic)
            notify("render", f"Built clip {clip_rank}/{len(segments)} for video {video_rank}: {clip_path}")

            metadata = generate_metadata(topic, segment.text, settings.gemini_model, settings.gemini_api_key)
            notify("metadata", f"Generated metadata for video {video_rank} clip {clip_rank}: {metadata.title}")

            clip = GeneratedClip(
                run_id=clip_run_id,
                source_video=video,
                segment=segment,
                clip_path=clip_path,
                metadata=metadata,
                work_dir=clip_work_dir,
                video_rank=video_rank,
                clip_rank=clip_rank,
            )
            generated.append(clip)
            if on_clip_ready:
                try:
                    on_clip_ready(clip, video_rank, clip_rank)
                except Exception:
                    logger.exception("on_clip_ready callback raised (ignored)")

    return generated
