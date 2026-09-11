import time
from pathlib import Path

import requests

from content_engine.config import Settings
from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata, UploadResult
from content_engine.uploaders.base import Uploader

GRAPH_HOST = "https://graph.instagram.com"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300


class InstagramUploader(Uploader):
    """Publishes a Reel via the Instagram Graph API (Instagram Login variant).

    Instagram's container-creation call fetches the video from a URL - it cannot
    see a local file - so this requires the dashboard's own media server
    (`python dashboard.py`) to be reachable at INSTAGRAM_PUBLIC_VIDEO_BASE_URL
    (e.g. an ngrok tunnel pointed at it), running for the duration of the upload.
    See README for the one-time Meta Developer app / Instagram Business account setup.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def upload(self, video_path: Path, metadata: ClipMetadata, privacy_status: str) -> UploadResult:
        settings = self._settings
        if not settings.instagram_access_token or not settings.instagram_business_account_id:
            raise UploadFailedError(
                "Instagram is not configured: set INSTAGRAM_ACCESS_TOKEN and "
                "INSTAGRAM_BUSINESS_ACCOUNT_ID in .env"
            )
        if not settings.instagram_public_video_base_url:
            raise UploadFailedError(
                "INSTAGRAM_PUBLIC_VIDEO_BASE_URL is not set. Instagram fetches the video from "
                "a public URL - run a tunnel (e.g. `ngrok http 8000`) to the dashboard server "
                "and set this to the tunnel's HTTPS base."
            )

        # Our pipeline always writes the final clip to <work_dir>/<run_id>/clip_captioned.mp4,
        # and the dashboard's /media route serves that same path by run_id.
        run_id = video_path.parent.name
        video_url = f"{settings.instagram_public_video_base_url}/media/{run_id}/clip.mp4"

        caption = metadata.description
        if metadata.hashtags:
            caption = caption + "\n\n" + " ".join(f"#{tag}" for tag in metadata.hashtags)

        container_id = self._create_container(video_url, caption)
        self._wait_for_container_ready(container_id)
        media_id = self._publish_container(container_id)
        permalink = self._get_permalink(media_id)

        # Instagram has no per-post privacy flag - a Reel's visibility follows the
        # account's own public/private setting, not anything this call can control.
        return UploadResult(
            video_id=media_id,
            url=permalink or f"https://www.instagram.com/reel/{media_id}/",
            privacy_status=privacy_status,
        )

    def _create_container(self, video_url: str, caption: str) -> str:
        settings = self._settings
        url = f"{GRAPH_HOST}/{settings.instagram_graph_api_version}/{settings.instagram_business_account_id}/media"
        try:
            response = requests.post(
                url,
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "access_token": settings.instagram_access_token,
                },
                timeout=30,
            )
        except requests.RequestException as e:
            raise UploadFailedError(f"Instagram container creation request failed: {e}") from e

        data = response.json()
        if response.status_code != 200 or "id" not in data:
            raise UploadFailedError(f"Instagram container creation failed: {data}")
        return data["id"]

    def _wait_for_container_ready(self, container_id: str) -> None:
        settings = self._settings
        url = f"{GRAPH_HOST}/{settings.instagram_graph_api_version}/{container_id}"
        deadline = time.monotonic() + POLL_TIMEOUT_S

        while time.monotonic() < deadline:
            try:
                response = requests.get(
                    url,
                    params={"fields": "status_code", "access_token": settings.instagram_access_token},
                    timeout=30,
                )
                data = response.json()
            except requests.RequestException as e:
                raise UploadFailedError(f"Instagram container status check failed: {e}") from e

            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise UploadFailedError(f"Instagram container failed to process: {data}")
            time.sleep(POLL_INTERVAL_S)

        raise UploadFailedError("Timed out waiting for Instagram container to finish processing")

    def _publish_container(self, container_id: str) -> str:
        settings = self._settings
        url = f"{GRAPH_HOST}/{settings.instagram_graph_api_version}/{settings.instagram_business_account_id}/media_publish"
        try:
            response = requests.post(
                url,
                data={"creation_id": container_id, "access_token": settings.instagram_access_token},
                timeout=30,
            )
        except requests.RequestException as e:
            raise UploadFailedError(f"Instagram publish request failed: {e}") from e

        data = response.json()
        if response.status_code != 200 or "id" not in data:
            raise UploadFailedError(f"Instagram publish failed: {data}")
        return data["id"]

    def _get_permalink(self, media_id: str) -> str | None:
        settings = self._settings
        url = f"{GRAPH_HOST}/{settings.instagram_graph_api_version}/{media_id}"
        try:
            response = requests.get(
                url,
                params={"fields": "permalink", "access_token": settings.instagram_access_token},
                timeout=30,
            )
            data = response.json()
            return data.get("permalink")
        except requests.RequestException:
            return None
