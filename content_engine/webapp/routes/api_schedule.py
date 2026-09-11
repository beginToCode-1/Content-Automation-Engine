from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from content_engine.config import Settings
from content_engine.db import schedules_repo
from content_engine.webapp.deps import get_current_user, get_settings, require_admin

router = APIRouter(prefix="/api")

# Deliberately no privacy field here - scheduled runs are always forced to
# private inside the scheduler/pipeline, regardless of any other setting.


class NewScheduleRequest(BaseModel):
    topic: str
    recurrence: str
    platforms: list[str] = ["youtube"]
    scheduled_time: str | None = None  # ISO datetime, required for recurrence="once"
    daily_time: str | None = None  # "HH:MM", required for recurrence="daily"


@router.post("/schedule", status_code=201)
async def create_schedule(
    payload: NewScheduleRequest, settings: Settings = Depends(get_settings), user: dict = Depends(require_admin)
):
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    if payload.recurrence not in ("once", "daily"):
        raise HTTPException(status_code=400, detail="recurrence must be 'once' or 'daily'")

    scheduled_time_iso = None
    daily_time = None

    if payload.recurrence == "once":
        if not payload.scheduled_time:
            raise HTTPException(status_code=400, detail="scheduled_time is required for a 'once' schedule")
        try:
            dt = datetime.fromisoformat(payload.scheduled_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="scheduled_time must be an ISO datetime")
        scheduled_time_iso = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        if not payload.daily_time:
            raise HTTPException(status_code=400, detail="daily_time is required for a 'daily' schedule")
        daily_time = payload.daily_time

    schedule_id = schedules_repo.insert_schedule(
        settings.db_path,
        topic,
        payload.recurrence,
        payload.platforms or ["youtube"],
        scheduled_time=scheduled_time_iso,
        daily_time=daily_time,
        user_id=user["id"],
    )
    return {"id": schedule_id}


@router.get("/schedule")
async def list_schedules(settings: Settings = Depends(get_settings), user: dict = Depends(get_current_user)):
    return {"schedules": schedules_repo.list_active(settings.db_path, user["id"])}


@router.post("/schedule/{schedule_id}/cancel")
async def cancel_schedule(
    schedule_id: int, settings: Settings = Depends(get_settings), user: dict = Depends(require_admin)
):
    cancelled = schedules_repo.cancel(settings.db_path, schedule_id, user["id"])
    if not cancelled:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"cancelled": True}
