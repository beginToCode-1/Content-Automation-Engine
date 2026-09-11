import json

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from content_engine.errors import MetadataGenerationError
from content_engine.models import ClipMetadata

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
_MAX_HASHTAGS = 5


def generate_metadata(topic: str, segment_text: str, model: str, api_key: str) -> ClipMetadata:
    client = genai.Client(api_key=api_key)

    prompt = (
        f"Write YouTube Shorts metadata for a short video about: {topic!r}.\n\n"
        f"The video's spoken content (from its transcript) is:\n{segment_text}\n\n"
        "Produce a catchy, accurate title, a short description, and 3-5 relevant hashtags."
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
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

    if "shorts" not in title.lower():
        suffix = " #Shorts"
        title = title[: _MAX_TITLE_LEN - len(suffix)] + suffix
    title = title[:_MAX_TITLE_LEN]

    return ClipMetadata(title=title, description=description, hashtags=hashtags)
