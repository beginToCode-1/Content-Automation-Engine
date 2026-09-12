from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from content_engine.errors import UploadFailedError
from content_engine.models import ClipMetadata, UploadResult
from content_engine.uploaders.base import Uploader

DEFAULT_CATEGORY_ID = "22"  # People & Blogs
_MAX_TITLE_LEN = 100


class YouTubeUploader(Uploader):
    def __init__(self, client, category_id: str = DEFAULT_CATEGORY_ID):
        self._client = client
        self._category_id = category_id

    def upload(self, video_path: Path, metadata: ClipMetadata, privacy_status: str) -> UploadResult:
        description = metadata.description
        if metadata.hashtags:
            description = description + "\n\n" + " ".join(f"#{tag}" for tag in metadata.hashtags)

        title = metadata.title
        if "shorts" not in title.lower():
            suffix = " #Shorts"
            title = title[: _MAX_TITLE_LEN - len(suffix)] + suffix
        title = title[:_MAX_TITLE_LEN]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": metadata.hashtags,
                "categoryId": self._category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
        request = self._client.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        try:
            while response is None:
                _, response = request.next_chunk()
        except HttpError as e:
            raise UploadFailedError(f"YouTube upload failed: {e}") from e

        video_id = response["id"]
        return UploadResult(
            video_id=video_id,
            url=f"https://youtube.com/shorts/{video_id}",
            privacy_status=privacy_status,
        )
