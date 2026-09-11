from fastapi import APIRouter, Depends, HTTPException, Request

from content_engine.config import Settings
from content_engine.db import batches_repo, runs_repo, schedules_repo, uploads_repo
from content_engine.webapp.deps import channel_connection_status, get_settings, templates

router = APIRouter()


def _sidebar_context(settings: Settings) -> dict:
    return {
        "channels": channel_connection_status(settings),
        "runs_count": runs_repo.count_all(settings.db_path),
    }


@router.get("/")
def self_upload_page(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse(request, "self_upload.html", _sidebar_context(settings))


@router.get("/studio")
def index(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse(request, "index.html", _sidebar_context(settings))


@router.get("/runs")
def runs_library(request: Request, settings: Settings = Depends(get_settings)):
    runs = runs_repo.list_recent(settings.db_path, limit=200)
    for run in runs:
        run["platforms"] = runs_repo.platforms_from_str(run["target_platforms"])
    succeeded = sum(1 for r in runs if r["status"] == "succeeded")
    failed = sum(1 for r in runs if r["status"] == "failed")
    return templates.TemplateResponse(
        request,
        "runs_library.html",
        {**_sidebar_context(settings), "runs": runs, "succeeded_count": succeeded, "failed_count": failed},
    )


@router.get("/runs/{run_id}")
def run_detail(request: Request, run_id: str, settings: Settings = Depends(get_settings)):
    run = runs_repo.get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run["platforms"] = runs_repo.platforms_from_str(run["target_platforms"])

    events = runs_repo.list_events_since(settings.db_path, run_id, since_id=0)
    uploads = uploads_repo.list_uploads_for_run(settings.db_path, run_id)
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {**_sidebar_context(settings), "run": run, "events": events, "uploads": uploads},
    )


@router.get("/schedule")
def schedule_page(request: Request, settings: Settings = Depends(get_settings)):
    schedules = schedules_repo.list_active(settings.db_path)
    for entry in schedules:
        entry["platforms"] = runs_repo.platforms_from_str(entry["target_platforms"])
    return templates.TemplateResponse(
        request, "schedule.html", {**_sidebar_context(settings), "schedules": schedules}
    )


@router.get("/batch")
def batch_page(request: Request, settings: Settings = Depends(get_settings)):
    batches = batches_repo.list_recent_batches(settings.db_path, limit=20)
    for batch in batches:
        batch["platforms"] = runs_repo.platforms_from_str(batch["target_platforms"])
    return templates.TemplateResponse(
        request,
        "batch.html",
        {
            **_sidebar_context(settings),
            "batches": batches,
            "default_stagger_minutes": settings.batch_default_stagger_minutes,
            "max_videos": settings.batch_max_videos,
            "max_clips_per_video": settings.batch_max_clips_per_video,
        },
    )


@router.get("/batch/{batch_id}")
def batch_detail(request: Request, batch_id: str, settings: Settings = Depends(get_settings)):
    batch = batches_repo.get_batch(settings.db_path, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch["platforms"] = runs_repo.platforms_from_str(batch["target_platforms"])
    clips = runs_repo.list_runs_for_batch(settings.db_path, batch_id)
    return templates.TemplateResponse(
        request, "batch_detail.html", {**_sidebar_context(settings), "batch": batch, "clips": clips}
    )


@router.get("/privacy")
def privacy_page(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse(request, "privacy.html", _sidebar_context(settings))


@router.get("/terms")
def terms_page(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse(request, "terms.html", _sidebar_context(settings))
