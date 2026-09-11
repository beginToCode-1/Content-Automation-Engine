import asyncio
import logging
from datetime import datetime

from content_engine.config import Settings
from content_engine.db import runs_repo, schedules_repo
from content_engine.webapp import executor, upload_queue

logger = logging.getLogger("content_engine.webapp.scheduler")

_task: asyncio.Task | None = None


def start_scheduler(settings: Settings) -> None:
    global _task
    _task = asyncio.create_task(_scheduler_loop(settings))


def stop_scheduler() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None


async def _scheduler_loop(settings: Settings) -> None:
    while True:
        await asyncio.sleep(settings.scheduler_poll_interval_s)
        try:
            await _poll_once(settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler poll iteration failed")


async def _poll_once(settings: Settings) -> None:
    now = datetime.now()
    due_entries = await asyncio.to_thread(schedules_repo.find_due, settings.db_path, now)

    for entry in due_entries:
        platforms = runs_repo.platforms_from_str(entry["target_platforms"])
        run_id = executor.submit_run(
            settings,
            topic=entry["topic"],
            trigger_source="scheduled",
            target_platforms=platforms,
            dry_run=False,
            privacy_override=None,
            schedule_id=entry["id"],
            force_private=True,  # hardcoded literal - never derived from schedule data, by design
        )
        await asyncio.to_thread(schedules_repo.mark_triggered, settings.db_path, entry["id"], run_id, now)
        if entry["recurrence"] == "once":
            await asyncio.to_thread(schedules_repo.mark_completed, settings.db_path, entry["id"])
        logger.info("Scheduled topic %r triggered as run %s (forced private)", entry["topic"], run_id)

    due_uploads = await asyncio.to_thread(runs_repo.list_due_queued_uploads, settings.db_path, now)
    for run_row in due_uploads:
        await asyncio.to_thread(upload_queue.process_due_upload, settings, run_row)
        logger.info("Processed queued upload for run %s", run_row["run_id"])
