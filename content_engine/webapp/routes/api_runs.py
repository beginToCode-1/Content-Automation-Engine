import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from content_engine.config import Settings
from content_engine.db import runs_repo, uploads_repo
from content_engine.webapp import executor
from content_engine.webapp.account_selection import resolve_youtube_account_id
from content_engine.webapp.deps import get_current_user, get_db_pool, get_settings, require_admin

router = APIRouter(prefix="/api")

VALID_PLATFORMS = {"youtube", "instagram", "tiktok"}


def _ensure_owned(run: dict | None, user: dict) -> dict:
    """404s (never 403) when the run doesn't exist OR belongs to someone else -
    a 403 would leak that the run_id exists at all to a user who can't see it."""
    if run is None or run["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


class NewRunRequest(BaseModel):
    topic: str
    mode: str = "generate_and_upload"
    platforms: list[str] = ["youtube"]
    privacy: str | None = None
    youtube_account_id: str | None = None


@router.post("/runs", status_code=202)
async def create_run(
    payload: NewRunRequest,
    settings: Settings = Depends(get_settings),
    pool: ConnectionPool = Depends(get_db_pool),
    user: dict = Depends(require_admin),
):
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")

    platforms = payload.platforms or ["youtube"]
    unknown = set(platforms) - VALID_PLATFORMS
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown platform(s): {sorted(unknown)}")

    dry_run = payload.mode == "generate_only"
    youtube_account_id = resolve_youtube_account_id(pool, user, platforms, payload.youtube_account_id)

    run_id = await run_in_threadpool(
        executor.submit_run,
        settings,
        topic=topic,
        trigger_source="web",
        target_platforms=platforms,
        dry_run=dry_run,
        privacy_override=payload.privacy,
        user_id=user["id"],
        youtube_account_id=youtube_account_id,
    )
    return {"run_id": run_id}


@router.get("/runs")
async def list_runs(
    limit: int = 20, pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(get_current_user)
):
    runs = await run_in_threadpool(runs_repo.list_recent, pool, limit, user["id"])
    return {"runs": runs}


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: str,
    since_id: int = 0,
    pool: ConnectionPool = Depends(get_db_pool),
    user: dict = Depends(get_current_user),
):
    run = await run_in_threadpool(runs_repo.get_run, pool, run_id)
    _ensure_owned(run, user)
    events = await run_in_threadpool(runs_repo.list_events_since, pool, run_id, since_id)
    uploads = await run_in_threadpool(uploads_repo.list_uploads_for_run, pool, run_id)
    return {"run": run, "events": events, "uploads": uploads}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    settings: Settings = Depends(get_settings),
    pool: ConnectionPool = Depends(get_db_pool),
    user: dict = Depends(require_admin),
):
    run = await run_in_threadpool(runs_repo.get_run, pool, run_id)
    _ensure_owned(run, user)
    cancelled = await run_in_threadpool(executor.cancel_run, settings, run_id)
    if not cancelled:
        raise HTTPException(
            status_code=409, detail="Run could not be cancelled (already finished, or unknown)"
        )
    return {"cancelled": True}


@router.post("/runs/{run_id}/retry", status_code=202)
async def retry_run(
    run_id: str,
    settings: Settings = Depends(get_settings),
    pool: ConnectionPool = Depends(get_db_pool),
    user: dict = Depends(require_admin),
):
    run = await run_in_threadpool(runs_repo.get_run, pool, run_id)
    _ensure_owned(run, user)
    if run["status"] not in ("failed", "cancelled"):
        raise HTTPException(status_code=409, detail="Only failed or cancelled runs can be retried")

    platforms = runs_repo.platforms_from_str(run["target_platforms"])
    privacy = run["requested_privacy"]

    if run["source_type"] == "own_upload":
        # The uploaded file and generated metadata were never the problem (the
        # upload attempt was) - retry re-attempts only the upload step against
        # the same clip, instead of restarting a pipeline that doesn't apply here.
        # Claim the run atomically first: a compare-and-set on status='failed'
        # so a double-click or a second tab hitting /retry concurrently can't
        # both pass this check and re-publish the same run_id twice.
        claimed = await run_in_threadpool(runs_repo.try_reclaim_failed, pool, run_id)
        if not claimed:
            raise HTTPException(status_code=409, detail="This run is already being retried")

        clip_path = Path(run["clip_path"]) if run["clip_path"] else None
        if not clip_path or not clip_path.exists():
            await run_in_threadpool(
                runs_repo.mark_failed,
                pool,
                run_id,
                "Original video file is no longer available on disk for retry",
            )
            raise HTTPException(
                status_code=409, detail="Original video file is no longer available on disk for retry"
            )
        from content_engine.models import ClipMetadata
        from content_engine.webapp.routes.api_self_upload import _publish

        metadata = ClipMetadata(
            title=run["metadata_title"] or "",
            description=run["metadata_description"] or "",
            hashtags=json.loads(run["metadata_hashtags"]) if run["metadata_hashtags"] else [],
        )
        effective_privacy = run["effective_privacy"] or privacy or settings.upload_privacy_status
        executor.run_in_background(
            _publish,
            settings,
            run_id,
            clip_path,
            metadata,
            platforms,
            effective_privacy,
            run["topic"],
            run["youtube_account_id"],
        )
        return {"run_id": run_id}

    new_run_id = await run_in_threadpool(
        executor.submit_run,
        settings,
        topic=run["topic"],
        trigger_source="web",
        target_platforms=platforms,
        dry_run=False,
        privacy_override=privacy,
        user_id=user["id"],
        # Retry reuses the account the original run was tied to - if it was
        # disconnected since then, get_youtube_client_for_account raises a
        # clear ConfigError that surfaces as this run's failure message,
        # rather than silently re-resolving to some other connected account.
        youtube_account_id=run["youtube_account_id"],
    )
    return {"run_id": new_run_id}


@router.post("/runs/{run_id}/cancel-upload")
async def cancel_scheduled_upload(
    run_id: str, pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(require_admin)
):
    run = await run_in_threadpool(runs_repo.get_run, pool, run_id)
    _ensure_owned(run, user)
    if not run.get("scheduled_upload_at"):
        raise HTTPException(status_code=409, detail="This run has no pending scheduled upload")

    await run_in_threadpool(uploads_repo.skip_pending_uploads, pool, run_id)
    await run_in_threadpool(runs_repo.clear_scheduled_upload, pool, run_id)
    return {"cancelled": True}
