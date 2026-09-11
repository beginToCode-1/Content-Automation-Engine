import uvicorn

from content_engine.config import Settings

if __name__ == "__main__":
    settings = Settings.load()
    uvicorn.run(
        "content_engine.webapp.app:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
    )
