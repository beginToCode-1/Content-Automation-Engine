import time
from pathlib import Path

import requests

from content_engine.auth import tiktok_oauth
from content_engine.config import Settings
from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata, UploadResult
from content_engine.uploaders.base import Uploader

API_HOST = "https://open.tiktokapis.com"
PRIVACY_PRIORITY = ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"]
POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 120
MAX_SINGLE_CHUNK_BYTES = 50 * 1024 * 1024


def _status_retryable(status_code: int) -> bool:
    """5xx and 429 look transient; anything else (4xx auth/validation) won't
    be fixed by retrying."""
    return status_code >= 500 or status_code == 429


class TikTokUploader(Uploader):
    """Uploads via TikTok's Content Posting API (single-chunk FILE_UPLOAD - fine
    for our ~30-60s vertical clips). Unaudited apps are restricted by TikTok
    itself to private/draft posts visible only to the developer's own account,
    which is what makes this safe to test with real credentials. See README for
    the one-time TikTok Developer app / OAuth setup.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def upload(self, video_path: Path, metadata: ClipMetadata, privacy_status: str) -> UploadResult:
        access_token = tiktok_oauth.get_access_token(self._settings)
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}

        privacy_level = self._choose_privacy_level(headers)

        video_size = video_path.stat().st_size
        if video_size > MAX_SINGLE_CHUNK_BYTES:
            raise UploadFailedError(
                f"Clip is {video_size} bytes, larger than the {MAX_SINGLE_CHUNK_BYTES}-byte "
                "single-chunk upload limit this uploader supports"
            )

        publish_id, upload_url = self._init_upload(headers, metadata, privacy_level, video_size)
        self._upload_bytes(upload_url, video_path, video_size)
        self._wait_for_publish(headers, publish_id)

        # An unaudited/private post has no public watch URL - only visible in the
        # developer's own TikTok app drafts/private posts.
        return UploadResult(video_id=publish_id, url="", privacy_status=privacy_level)

    def _choose_privacy_level(self, headers: dict) -> str:
        try:
            response = requests.post(f"{API_HOST}/v2/post/publish/creator_info/query/", headers=headers, timeout=30)
            data = response.json()
        except requests.RequestException as e:
            raise UploadFailedError(f"TikTok creator_info query failed: {e}", retryable=True) from e

        if response.status_code != 200 or data.get("error", {}).get("code") != "ok":
            raise UploadFailedError(
                f"TikTok creator_info query failed: {data}", retryable=_status_retryable(response.status_code)
            )

        options = data.get("data", {}).get("privacy_level_options", [])
        for candidate in PRIVACY_PRIORITY:
            if candidate in options:
                return candidate
        if options:
            return options[0]
        raise UploadFailedError("TikTok returned no privacy_level_options for this account")

    def _init_upload(
        self, headers: dict, metadata: ClipMetadata, privacy_level: str, video_size: int
    ) -> tuple[str, str]:
        body = {
            "post_info": {
                "title": metadata.title,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 0,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        }
        try:
            response = requests.post(f"{API_HOST}/v2/post/publish/video/init/", headers=headers, json=body, timeout=30)
            data = response.json()
        except requests.RequestException as e:
            raise UploadFailedError(f"TikTok video init failed: {e}", retryable=True) from e

        if response.status_code != 200 or data.get("error", {}).get("code") != "ok":
            raise UploadFailedError(
                f"TikTok video init failed: {data}", retryable=_status_retryable(response.status_code)
            )

        inner = data["data"]
        return inner["publish_id"], inner["upload_url"]

    def _upload_bytes(self, upload_url: str, video_path: Path, video_size: int) -> None:
        video_bytes = video_path.read_bytes()
        put_headers = {
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
            "Content-Type": "video/mp4",
        }
        try:
            response = requests.put(upload_url, data=video_bytes, headers=put_headers, timeout=120)
        except requests.RequestException as e:
            raise UploadFailedError(f"TikTok video byte upload failed: {e}", retryable=True) from e

        if response.status_code not in (200, 201):
            raise UploadFailedError(
                f"TikTok video byte upload failed: HTTP {response.status_code} {response.text}",
                retryable=_status_retryable(response.status_code),
            )

    def _wait_for_publish(self, headers: dict, publish_id: str) -> None:
        deadline = time.monotonic() + POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                response = requests.post(
                    f"{API_HOST}/v2/post/publish/status/fetch/",
                    headers=headers,
                    json={"publish_id": publish_id},
                    timeout=30,
                )
                data = response.json()
            except requests.RequestException as e:
                raise UploadFailedError(f"TikTok status fetch failed: {e}", retryable=True) from e

            status = data.get("data", {}).get("status")
            if status == "PUBLISH_COMPLETE":
                return
            if status == "FAILED":
                raise UploadFailedError(f"TikTok publish failed: {data}")
            time.sleep(POLL_INTERVAL_S)

        raise UploadFailedError("Timed out waiting for TikTok publish to complete", retryable=True)
