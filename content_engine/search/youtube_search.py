import re

from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from content_engine.errors import SearchFailedError
from content_engine.models import VideoCandidate
from content_engine.scoring import relevance_scores

_ISO8601_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def _parse_iso8601_duration(value: str) -> float:
    match = _ISO8601_DURATION_RE.fullmatch(value)
    if not match:
        return 0.0
    parts = match.groupdict(default="0")
    days, hours, minutes, seconds = (int(parts[k]) for k in ("days", "hours", "minutes", "seconds"))
    return float(days * 86400 + hours * 3600 + minutes * 60 + seconds)


def search_videos(topic: str, max_results: int = 15, client: Resource | None = None) -> list[VideoCandidate]:
    """Search YouTube for videos relevant to `topic`. Requires a pre-built client
    (either API-key or OAuth authorized) since search.list needs credentials of
    one form or another.
    """
    if client is None:
        raise SearchFailedError("search_videos() requires a YouTube API client")

    try:
        search_response = (
            client.search()
            .list(
                q=topic,
                part="snippet",
                type="video",
                maxResults=max_results,
                relevanceLanguage="en",
                safeSearch="strict",
            )
            .execute()
        )
    except HttpError as e:
        raise SearchFailedError(f"YouTube search.list failed: {e}") from e

    # search.list can occasionally return items without a videoId (e.g. a result
    # that lost its video association between indexing and this request) even
    # with type="video" set - skip those rather than crashing on a KeyError.
    video_ids = [
        item["id"]["videoId"] for item in search_response.get("items", []) if item.get("id", {}).get("videoId")
    ]
    if not video_ids:
        raise SearchFailedError(f"No YouTube search results for topic: {topic!r}")

    try:
        details_response = (
            client.videos()
            .list(part="contentDetails,statistics,snippet", id=",".join(video_ids))
            .execute()
        )
    except HttpError as e:
        raise SearchFailedError(f"YouTube videos.list failed: {e}") from e

    candidates = []
    for item in details_response.get("items", []):
        snippet = item["snippet"]
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        candidates.append(
            VideoCandidate(
                video_id=item["id"],
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                channel=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
                duration_s=_parse_iso8601_duration(content_details.get("duration", "PT0S")),
                view_count=int(statistics.get("viewCount", 0)) if statistics.get("viewCount") else None,
            )
        )

    if not candidates:
        raise SearchFailedError(f"No video details resolved for topic: {topic!r}")
    return candidates


def select_best(candidates: list[VideoCandidate], topic: str, min_duration_s: int = 90) -> VideoCandidate:
    eligible = [c for c in candidates if (c.duration_s or 0) >= min_duration_s]
    if not eligible:
        raise SearchFailedError(
            f"No candidate video is long enough (>= {min_duration_s}s) to extract a short segment from"
        )

    documents = [f"{c.title} {c.description}" for c in eligible]
    scores = relevance_scores(topic, documents)
    for candidate, score in zip(eligible, scores):
        candidate.score = score

    eligible.sort(key=lambda c: (c.score or 0.0, c.view_count or 0), reverse=True)
    return eligible[0]


def select_top(candidates: list[VideoCandidate], topic: str, count: int, min_duration_s: int = 90) -> list[VideoCandidate]:
    """Same eligibility filter and scoring as select_best, but returns the top
    `count` distinct videos instead of one. Returns fewer than `count` if fewer
    eligible candidates exist - callers must handle a shorter-than-requested list."""
    eligible = [c for c in candidates if (c.duration_s or 0) >= min_duration_s]
    if not eligible:
        raise SearchFailedError(
            f"No candidate video is long enough (>= {min_duration_s}s) to extract a short segment from"
        )

    documents = [f"{c.title} {c.description}" for c in eligible]
    scores = relevance_scores(topic, documents)
    for candidate, score in zip(eligible, scores):
        candidate.score = score

    eligible.sort(key=lambda c: (c.score or 0.0, c.view_count or 0), reverse=True)
    return eligible[:count]


def build_search_client(api_key: str | None, oauth_client: Resource | None) -> Resource:
    if api_key:
        return build("youtube", "v3", developerKey=api_key)
    if oauth_client is not None:
        return oauth_client
    raise SearchFailedError("No YouTube API key or OAuth client available for search")
