import json
import logging
from pathlib import Path

from content_engine.config import Settings
from content_engine.db import runs_repo, uploads_repo
from content_engine.models import ClipMetadata, PlatformUploadOutcome
from content_engine.pipeline import upload_clip_to_platforms

logger = logging.getLogger("content_engine.webapp.upload_queue")


def process_due_upload(settings: Settings, run_row: dict) -> None:
    """Called by the scheduler for a run whose deferred upload time has arrived.
    Runs synchronously - the caller (scheduler) is expected to invoke this via
    asyncio.to_thread so it doesn't block the event loop.
    """
    run_id = run_row["run_id"]
    pending_uploads = uploads_repo.list_uploads_for_run(settings.db_path, run_id)
    platforms = [u["platform"] for u in pending_uploads if u["status"] == "pending"]
    if not platforms:
        runs_repo.clear_scheduled_upload(settings.db_path, run_id)
        return

    # Flip to 'uploading' and clear the schedule BEFORE any network call, so a
    # crash mid-upload leaves a visible 'uploading' row (cleaned up by
    # sweep_stale_uploading on next startup) rather than silently re-matching
    # list_due_queued_uploads() on the next poll tick.
    uploads_repo.mark_uploading(settings.db_path, run_id)
    runs_repo.clear_scheduled_upload(settings.db_path, run_id)

    metadata = ClipMetadata(
        title=run_row["metadata_title"] or "",
        description=run_row["metadata_description"] or "",
        hashtags=json.loads(run_row["metadata_hashtags"]) if run_row["metadata_hashtags"] else [],
    )
    clip_path = Path(run_row["clip_path"])
    effective_privacy = run_row["effective_privacy"] or settings.upload_privacy_status

    def on_progress(stage: str, message: str) -> None:
        runs_repo.append_event(settings.db_path, run_id, stage, message)

    try:
        outcomes = upload_clip_to_platforms(
            clip_path,
            metadata,
            platforms,
            settings,
            effective_privacy,
            run_row["topic"],
            run_id,
            on_progress=on_progress,
            raise_if_all_failed=False,
        )
    except Exception as e:
        logger.exception("Unexpected error processing queued upload for run %s", run_id)
        uploads_repo.record_upload_outcomes(
            settings.db_path,
            run_id,
            [PlatformUploadOutcome(platform=p, result=None, error=str(e)) for p in platforms],
        )
        runs_repo.mark_failed(settings.db_path, run_id, f"Queued upload failed: {e}")
        return

    uploads_repo.record_upload_outcomes(settings.db_path, run_id, outcomes)

    if any(o.result for o in outcomes):
        runs_repo.mark_succeeded(settings.db_path, run_id)
    else:
        error_message = "All requested platform uploads failed: " + "; ".join(
            f"{o.platform}: {o.error}" for o in outcomes
        )
        runs_repo.mark_failed(settings.db_path, run_id, error_message)
