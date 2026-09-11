from abc import ABC, abstractmethod
from pathlib import Path

from content_engine.models import ClipMetadata, UploadResult


class Uploader(ABC):
    @abstractmethod
    def upload(self, video_path: Path, metadata: ClipMetadata, privacy_status: str) -> UploadResult:
        raise NotImplementedError
