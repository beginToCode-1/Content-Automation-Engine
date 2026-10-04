import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from content_engine.db import schedules_repo
from content_engine.webapp.account_selection import resolve_youtube_account_id
from content_engine.webapp.routes.api_runs import VALID_PLATFORMS, clean_topic
from content_engine.webapp.deps import get_current_user, get_db_pool, require_admin

router = APIRouter(prefix="/api")

# find_due() compares this lexicographically against the current "HH:MM", so
# an unpadded hour (e.g. client-supplied "9:00") would sort after "10:15" and
# never fire - this is the only thing standing between the DB and that bug.
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Deliberately no privacy field here - scheduled runs are always forced to
# private inside the scheduler/pipeline, regardless of any other setting.


class NewScheduleRequest(BaseModel):
    topic: str
    recurrence: str
    platforms: list[str] = ["youtube"]
    scheduled_time: str | None = None  # ISO datetime, required for recurrence="once"
    daily_time: str | None = None  # "HH:MM" in UTC, required for recurrence="daily"
    youtube_account_id: str | None = None


@router.post("/schedule", status_code=201)
def create_schedule(
    payload: NewScheduleRequest,
    pool: ConnectionPool = Depends(get_db_pool),
    user: dict = Depends(require_admin),
):
    topic = clean_topic(payload.topic)
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
        # Everything is scheduled in UTC. The web app sends an ISO time with an
        # offset; a time without one is taken to already be UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        scheduled_time_iso = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        if not payload.daily_time or not _HHMM_RE.match(payload.daily_time):
            raise HTTPException(status_code=400, detail="daily_time must be in 24-hour HH:MM format (e.g. 09:00)")
        daily_time = payload.daily_time

    platforms = payload.platforms or ["youtube"]
    unknown = set(platforms) - VALID_PLATFORMS
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown platform(s): {sorted(unknown)}")
    youtube_account_id = resolve_youtube_account_id(pool, user, platforms, payload.youtube_account_id)

    schedule_id = schedules_repo.insert_schedule(
        pool,
        topic,
        payload.recurrence,
        platforms,
        scheduled_time=scheduled_time_iso,
        daily_time=daily_time,
        user_id=user["id"],
        youtube_account_id=youtube_account_id,
    )
    return {"id": schedule_id}


@router.get("/schedule")
def list_schedules(pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(get_current_user)):
    return {"schedules": schedules_repo.list_active(pool, user["id"])}


@router.post("/schedule/{schedule_id}/cancel")
def cancel_schedule(
    schedule_id: int, pool: ConnectionPool = Depends(get_db_pool), user: dict = Depends(require_admin)
):
    cancelled = schedules_repo.cancel(pool, schedule_id, user["id"])
    if not cancelled:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"cancelled": True}
