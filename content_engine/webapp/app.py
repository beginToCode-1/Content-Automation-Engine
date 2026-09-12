import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from content_engine.config import Settings
from content_engine.db.connection import init_db
from content_engine.db import runs_repo, uploads_repo
from content_engine.webapp import executor, scheduler
from content_engine.webapp.routes import (
    api_auth,
    api_batches,
    api_meta,
    api_oauth,
    api_runs,
    api_schedule,
    api_self_upload,
    media,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    settings = Settings.load()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.db_path)
        swept_runs = await run_in_threadpool(runs_repo.sweep_stale_running, settings.db_path)
        swept_uploads = await run_in_threadpool(uploads_repo.sweep_stale_uploading, settings.db_path)
        if swept_runs:
            print(f"Marked {swept_runs} interrupted run(s) as failed on startup.")
        if swept_uploads:
            print(f"Marked {swept_uploads} interrupted upload(s) as failed on startup.")
        executor.init_executor(settings.dashboard_max_workers)
        scheduler.start_scheduler(settings)
        try:
            yield
        finally:
            scheduler.stop_scheduler()
            executor.shutdown_executor()

    app = FastAPI(title="Content Automation Engine Dashboard", lifespan=lifespan)
    app.state.settings = settings

    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # The old server-rendered Jinja dashboard (content_engine/webapp/routes/pages.py)
    # is intentionally NOT mounted here: it queried the DB directly with no auth
    # at all, which would leak every user's runs/batches/schedules to anyone who
    # hit this backend's URL now that the real UI (web/, on Vercel) requires
    # login. The Next.js frontend fully replaces it, including /privacy and /terms.
    app.include_router(api_auth.router)
    app.include_router(api_runs.router)
    app.include_router(api_schedule.router)
    app.include_router(api_batches.router)
    app.include_router(api_self_upload.router)
    app.include_router(api_meta.router)
    app.include_router(api_oauth.router)
    app.include_router(media.router)

    return app


app = create_app()
