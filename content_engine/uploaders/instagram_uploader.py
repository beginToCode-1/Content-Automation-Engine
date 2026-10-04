import time
from pathlib import Path

import requests

from content_engine import tunnel
from content_engine.config import Settings
from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata, UploadResult
from content_engine.uploaders.base import Uploader

GRAPH_HOST = "https://graph.instagram.com"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300


def _json(response: requests.Response) -> dict:
    """Error pages (e.g. a proxy's HTML 502) aren't JSON - treat them as an empty body."""
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _status_retryable(status_code: int) -> bool:
    """5xx and 429 look transient; anything else (4xx auth/validation) won't
    be fixed by retrying."""
    return status_code >= 500 or status_code == 429


class InstagramUploader(Uploader):
    """Publishes a Reel via the Instagram Graph API (Instagram Login variant).

    Instagram's container-creation call fetches the video from a URL - it cannot
    see a local file - so this requires the dashboard's own media server
    (`python dashboard.py`) to be reachable at a public URL. That's either an
    explicit INSTAGRAM_PUBLIC_VIDEO_BASE_URL, or - if that's unset - a fresh
    ngrok tunnel started automatically at boot (see content_engine.tunnel),
    opted into via NGROK_AUTHTOKEN. See README for the one-time Meta Developer
    app / Instagram Business account setup.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def upload(self, video_path: Path, metadata: ClipMetadata, privacy_status: str) -> UploadResult:
        settings = self._settings
        # Instagram has no per-post privacy: a Reel is as visible as the account.
        # So anything but an explicit "public" request is refused, rather than
        # publishing it and reporting it as private (scheduled runs are forced private).
        if privacy_status != "public":
            raise UploadFailedError(
                f"Instagram can't post a '{privacy_status}' Reel: Instagram has no per-post privacy, "
                "so only runs with privacy set to 'public' are uploaded there."
            )
        if not settings.instagram_access_token or not settings.instagram_business_account_id:
            raise UploadFailedError(
                "Instagram is not configured: set INSTAGRAM_ACCESS_TOKEN and "
                "INSTAGRAM_BUSINESS_ACCOUNT_ID in .env"
            )
        base_url = settings.instagram_public_video_base_url or tunnel.get_public_url()
        if not base_url:
            raise UploadFailedError(
                "No public video base URL available. Instagram fetches the video from a public "
                "URL - either set INSTAGRAM_PUBLIC_VIDEO_BASE_URL to a tunnel's HTTPS base "
                "(e.g. `ngrok http 8000`), or set NGROK_AUTHTOKEN to have one start automatically."
            )

        # Our pipeline always writes the final clip to <work_dir>/<run_id>/clip_captioned.mp4,
        # and the dashboard's /media route serves that same path by run_id.
        run_id = video_path.parent.name
        video_url = f"{base_url}/media/{run_id}/clip.mp4"

        caption = metadata.description
        if metadata.hashtags:
            caption = caption + "\n\n" + " ".join(f"#{tag}" for tag in metadata.hashtags)

        container_id = self._create_container(video_url, caption)
        self._wait_for_container_ready(container_id)
        media_id = self._publish_container(container_id)
        permalink = self._get_permalink(media_id)

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
            raise UploadFailedError(f"Instagram container creation request failed: {e}", retryable=True) from e

        data = _json(response)
        if response.status_code != 200 or "id" not in data:
            raise UploadFailedError(
                f"Instagram container creation failed: {data}", retryable=_status_retryable(response.status_code)
            )
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
            except requests.RequestException as e:
                raise UploadFailedError(f"Instagram container status check failed: {e}", retryable=True) from e
            data = _json(response)
            if response.status_code != 200:
                # e.g. an expired token: no status_code field, so without this the
                # loop would sleep until the deadline and then retry the whole upload.
                raise UploadFailedError(
                    f"Instagram container status check failed: {data or response.status_code}",
                    retryable=_status_retryable(response.status_code),
                )

            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise UploadFailedError(f"Instagram container failed to process: {data}")
            time.sleep(POLL_INTERVAL_S)

        raise UploadFailedError("Timed out waiting for Instagram container to finish processing", retryable=True)

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
            # Not retryable: the Reel may already be live at Meta, and a retry
            # would create and publish a second one.
            raise UploadFailedError(
                f"Instagram publish request failed (the Reel may still have been posted - check the account): {e}"
            ) from e

        data = _json(response)
        if response.status_code != 200 or "id" not in data:
            raise UploadFailedError(
                f"Instagram publish failed (check the account before retrying): {data or response.status_code}"
            )
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
            return _json(response).get("permalink")
        except requests.RequestException:
            return None
