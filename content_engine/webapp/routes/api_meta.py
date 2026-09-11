from fastapi import APIRouter, Depends

from content_engine.config import Settings
from content_engine.db import runs_repo
from content_engine.webapp.deps import channel_connection_status, get_current_user, get_settings

router = APIRouter(prefix="/api")


@router.get("/meta")
async def get_meta(settings: Settings = Depends(get_settings), user: dict = Depends(get_current_user)):
    return {
        "channels": channel_connection_status(settings, user["id"]),
        "runs_count": runs_repo.count_all(settings.db_path, user["id"]),
        "batch_defaults": {
            "default_stagger_minutes": settings.batch_default_stagger_minutes,
            "max_videos": settings.batch_max_videos,
            "max_clips_per_video": settings.batch_max_clips_per_video,
        },
    }
