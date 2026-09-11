from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VideoCandidate:
    video_id: str
    title: str
    description: str
    channel: str
    published_at: str
    duration_s: float | None = None
    view_count: int | None = None
    score: float | None = None


@dataclass
class TranscriptLine:
    text: str
    start: float
    duration: float


@dataclass
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str
    lines: list[TranscriptLine]
    score: float


@dataclass
class DownloadResult:
    video_path: Path
    info_json_path: Path
    duration_s: float


@dataclass
class ClipMetadata:
    title: str
    description: str
    hashtags: list[str] = field(default_factory=list)


@dataclass
class UploadResult:
    video_id: str
    url: str
    privacy_status: str


@dataclass
class PlatformUploadOutcome:
    platform: str
    result: UploadResult | None
    error: str | None = None


@dataclass
class GeneratedClip:
    run_id: str
    source_video: VideoCandidate
    segment: TranscriptSegment
    clip_path: Path
    metadata: ClipMetadata
    work_dir: Path
    video_rank: int
    clip_rank: int


@dataclass
class PipelineResult:
    run_id: str
    topic: str
    source_video: VideoCandidate
    segment: TranscriptSegment
    clip_path: Path
    metadata: ClipMetadata
    upload: UploadResult | None
    work_dir: Path
    uploads: list[PlatformUploadOutcome] = field(default_factory=list)
