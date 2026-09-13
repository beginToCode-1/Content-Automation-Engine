from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from content_engine.config import Settings
from content_engine.db import batches_repo, runs_repo
from content_engine.webapp import batch_executor
from content_engine.webapp.account_selection import resolve_youtube_account_id
from content_engine.webapp.deps import get_current_user, get_db_pool, get_settings, require_admin
from content_engine.webapp.routes.api_runs import VALID_PLATFORMS

router = APIRouter(prefix="/api")


class NewBatchRequest(BaseModel):
    topic: str
    platforms: list[str] = ["youtube"]
    videos_count: int
    clips_per_video: int
    stagger_gap_minutes: int
    privacy: str | None = None
    youtube_account_id: str | None = None


@router.get("/batches")
async def list_batches(
    limit: int = 20, pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(get_current_user)
):
    batches = await run_in_threadpool(batches_repo.list_recent_batches, pool, limit, user["id"])
    for batch in batches:
        batch["platforms"] = runs_repo.platforms_from_str(batch["target_platforms"])
    return {"batches": batches}


@router.post("/batches", status_code=202)
async def create_batch(
    payload: NewBatchRequest,
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

    if not (1 <= payload.videos_count <= settings.batch_max_videos):
        raise HTTPException(status_code=400, detail=f"videos_count must be between 1 and {settings.batch_max_videos}")
    if not (1 <= payload.clips_per_video <= settings.batch_max_clips_per_video):
        raise HTTPException(
            status_code=400, detail=f"clips_per_video must be between 1 and {settings.batch_max_clips_per_video}"
        )
    if payload.stagger_gap_minutes < 1:
        raise HTTPException(status_code=400, detail="stagger_gap_minutes must be at least 1")

    youtube_account_id = resolve_youtube_account_id(pool, user, platforms, payload.youtube_account_id)

    batch_id = await run_in_threadpool(
        batch_executor.submit_batch,
        settings,
        topic=topic,
        target_platforms=platforms,
        videos_count=payload.videos_count,
        clips_per_video=payload.clips_per_video,
        stagger_gap_minutes=payload.stagger_gap_minutes,
        privacy_override=payload.privacy,
        user_id=user["id"],
        youtube_account_id=youtube_account_id,
    )
    return {"batch_id": batch_id}


@router.get("/batches/{batch_id}")
async def get_batch_status(
    batch_id: str, pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(get_current_user)
):
    batch = await run_in_threadpool(batches_repo.get_batch, pool, batch_id)
    if batch is None or batch["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Batch not found")
    clips = await run_in_threadpool(runs_repo.list_runs_for_batch, pool, batch_id)
    return {"batch": batch, "clips": clips}
