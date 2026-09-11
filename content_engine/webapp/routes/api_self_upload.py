import json
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from content_engine.config import Settings
from content_engine.db import runs_repo, uploads_repo
from content_engine.errors import MetadataGenerationError
from content_engine.metadata.generate_metadata import generate_metadata
from content_engine.models import ClipMetadata
from content_engine.pipeline import upload_clip_to_platforms
from content_engine.render.clip_builder import CLIP_FILENAME
from content_engine.webapp import executor
from content_engine.webapp.deps import get_settings
from content_engine.webapp.routes.api_runs import VALID_PLATFORMS

router = APIRouter(prefix="/api")


@router.post("/self-upload/draft")
async def create_draft(
    file: UploadFile = File(...),
    hint: str = Form(...),
    settings: Settings = Depends(get_settings),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only .mp4 files are supported in this version")

    hint = hint.strip()
    if not hint:
        raise HTTPException(status_code=400, detail="A short topic/context hint is required")

    draft_id = uuid.uuid4().hex[:10]
    draft_dir = settings.work_dir / draft_id
    draft_dir.mkdir(parents=True, exist_ok=True)
    dest_path = draft_dir / CLIP_FILENAME

    with dest_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    (draft_dir / "draft.json").write_text(
        json.dumps({"hint": hint, "original_filename": filename}), encoding="utf-8"
    )

    try:
        metadata = await run_in_threadpool(
            generate_metadata, hint, hint, settings.gemini_model, settings.gemini_api_key
        )
    except MetadataGenerationError as e:
        raise HTTPException(status_code=502, detail=f"Metadata generation failed: {e}")

    return {
        "draft_id": draft_id,
        "metadata": {
            "title": metadata.title,
            "description": metadata.description,
            "hashtags": metadata.hashtags,
        },
    }


class PublishDraftRequest(BaseModel):
    title: str
    description: str
    hashtags: list[str] = []
    platforms: list[str] = ["youtube"]
    privacy: str | None = None


@router.post("/self-upload/{draft_id}/publish", status_code=202)
async def publish_draft(draft_id: str, payload: PublishDraftRequest, settings: Settings = Depends(get_settings)):
    draft_dir = settings.work_dir / draft_id
    clip_path = draft_dir / CLIP_FILENAME
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Draft not found or already published")

    platforms = payload.platforms or ["youtube"]
    unknown = set(platforms) - VALID_PLATFORMS
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown platform(s): {sorted(unknown)}")
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title is required")

    draft_meta_path = draft_dir / "draft.json"
    draft_meta = json.loads(draft_meta_path.read_text(encoding="utf-8")) if draft_meta_path.exists() else {}
    topic = draft_meta.get("hint", draft_id)

    metadata = ClipMetadata(title=payload.title.strip(), description=payload.description, hashtags=payload.hashtags)
    effective_privacy = payload.privacy or settings.upload_privacy_status

    await run_in_threadpool(
        runs_repo.insert_run,
        settings.db_path,
        draft_id,
        topic,
        "web",
        platforms,
        False,
        payload.privacy,
        None,
        str(draft_dir),
    )
    await run_in_threadpool(
        runs_repo.update_fields,
        settings.db_path,
        draft_id,
        source_type="own_upload",
        clip_path=str(clip_path),
        metadata_title=metadata.title,
        metadata_description=metadata.description,
        metadata_hashtags=json.dumps(metadata.hashtags),
        effective_privacy=effective_privacy,
    )

    executor.run_in_background(_publish, settings, draft_id, clip_path, metadata, platforms, effective_privacy, topic)
    return {"run_id": draft_id}


def _publish(settings: Settings, run_id: str, clip_path, metadata: ClipMetadata, platforms, effective_privacy, topic):
    runs_repo.mark_running(settings.db_path, run_id)

    def on_progress(stage: str, message: str) -> None:
        runs_repo.append_event(settings.db_path, run_id, stage, message)

    try:
        outcomes = upload_clip_to_platforms(
            clip_path,
            metadata,
            platforms,
            settings,
            effective_privacy,
            topic,
            run_id,
            on_progress=on_progress,
            raise_if_all_failed=False,
        )
    except Exception as e:
        runs_repo.mark_failed(settings.db_path, run_id, f"Unexpected error: {e}")
        return

    uploads_repo.record_upload_outcomes(settings.db_path, run_id, outcomes)
    if any(o.result for o in outcomes):
        runs_repo.mark_succeeded(settings.db_path, run_id)
    else:
        error_message = "All requested platform uploads failed: " + "; ".join(
            f"{o.platform}: {o.error}" for o in outcomes
        )
        runs_repo.mark_failed(settings.db_path, run_id, error_message)
