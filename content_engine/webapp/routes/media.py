from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from content_engine.config import Settings
from content_engine.render.clip_builder import CLIP_FILENAME
from content_engine.webapp.deps import get_settings

router = APIRouter()


@router.get("/media/{run_id}/clip.mp4")
def get_clip(run_id: str, settings: Settings = Depends(get_settings)):
    # Served directly from the on-disk path convention (<work_dir>/<run_id>/CLIP_FILENAME)
    # rather than via the runs DB: this must work for CLI-triggered runs (which never
    # touch the DB) and must be fetchable by Instagram mid-run, before the DB row's
    # clip_path field is written back (that only happens after the whole run finishes).
    work_dir = settings.work_dir.resolve()
    clip_path = (work_dir / run_id / CLIP_FILENAME).resolve()

    if work_dir not in clip_path.parents:
        raise HTTPException(status_code=403, detail="Invalid run id")
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found")

    return FileResponse(clip_path, media_type="video/mp4")
