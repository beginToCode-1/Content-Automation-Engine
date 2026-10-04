import json
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from content_engine.errors import MetadataGenerationError
from content_engine.models import ClipMetadata, TranscriptSegment, VideoCandidate

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Catchy title, under 100 characters."},
        "description": {"type": "string", "description": "1-3 sentence description of the clip."},
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 relevant hashtags, without the # symbol.",
        },
    },
    "required": ["title", "description", "hashtags"],
}

_MAX_TITLE_LEN = 100
_SERVER_ERROR_WAITS_S = [5, 15, 30]
_MAX_HASHTAGS = 5


def generate_metadata(topic: str, segment_text: str, model: str, api_key: str) -> ClipMetadata:
    client = genai.Client(api_key=api_key)

    prompt = (
        f"Write YouTube Shorts metadata for a short video about: {topic!r}.\n\n"
        f"The video's spoken content (from its transcript) is:\n{segment_text}\n\n"
        "Produce a catchy, accurate title, a short description, and 3-5 relevant hashtags."
    )

    # Gemini returns 503 "high demand" in short bursts. This runs after the slow
    # render, so a few short retries beat failing the whole run.
    for attempt, wait_s in enumerate(_SERVER_ERROR_WAITS_S + [None]):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            )
            break
        except genai_errors.ServerError as e:
            if wait_s is None:
                raise MetadataGenerationError(f"Gemini API call failed after {attempt + 1} attempts: {e}") from e
            time.sleep(wait_s)
        except genai_errors.APIError as e:
            raise MetadataGenerationError(f"Gemini API call failed: {e}") from e

    if not response.text:
        raise MetadataGenerationError("Gemini response did not include any content")

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as e:
        raise MetadataGenerationError(f"Gemini response was not valid JSON: {e}") from e

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    hashtags = [str(h).lstrip("#").strip() for h in data.get("hashtags", []) if str(h).strip()][:_MAX_HASHTAGS]

    if not title:
        raise MetadataGenerationError("Gemini response produced an empty title")

    # No platform-specific branding here (e.g. "#Shorts") - this metadata is
    # shared verbatim across every requested platform's uploader; YouTube-only
    # touches belong in youtube_uploader.py instead.
    title = title[:_MAX_TITLE_LEN]

    return ClipMetadata(title=title, description=description, hashtags=hashtags)


def add_source_credit(metadata: ClipMetadata, video: VideoCandidate) -> ClipMetadata:
    """Every clip credits the creator and links the original video. It's the
    honest thing to do, and it's what reuse policies expect at a minimum."""
    credit = f'Original video: "{video.title}" by {video.channel}\nhttps://www.youtube.com/watch?v={video.video_id}'
    description = f"{metadata.description}\n\n{credit}" if metadata.description else credit
    return ClipMetadata(title=metadata.title, description=description, hashtags=metadata.hashtags)


_CHOICE_SCHEMA = {
    "type": "object",
    "properties": {"choice": {"type": "integer", "description": "Number of the best excerpt."}},
    "required": ["choice"],
}


def choose_segment(candidates: list[TranscriptSegment], topic: str, model: str, api_key: str) -> TranscriptSegment:
    """Asks Gemini which shortlisted excerpt works best as a standalone short.
    Keyword scoring finds on-topic windows; it can't judge whether a window
    opens with a hook or ends mid-thought. Any failure falls back to the
    best keyword score, so this can only improve the pick, never break a run."""
    by_score = max(candidates, key=lambda c: c.score)
    if by_score.score > 0:
        candidates = [c for c in candidates if c.score > 0]
    if len(candidates) <= 1:
        return by_score

    excerpts = "\n\n".join(f"Excerpt {i}:\n{c.text}" for i, c in enumerate(candidates, start=1))
    prompt = (
        f"These are transcript excerpts from a video. Pick the one that would make the best "
        f"standalone 30-60 second short video about {topic!r}: it should grab attention in the "
        "first sentence, make sense without the rest of the video, finish its thought, and stay "
        f"on topic.\n\n{excerpts}\n\nAnswer with the excerpt's number."
    )
    try:
        # Keep the client in a variable: an unreferenced Client is garbage-collected
        # (closing its HTTP connection) before the request is sent.
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=_CHOICE_SCHEMA),
        )
        choice = int(json.loads(response.text or "{}")["choice"])
    except Exception:
        return by_score
    if not 1 <= choice <= len(candidates):
        return by_score
    return candidates[choice - 1]
