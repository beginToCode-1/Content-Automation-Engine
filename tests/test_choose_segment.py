from unittest.mock import MagicMock, patch

from content_engine.metadata import generate_metadata as gm
from content_engine.models import TranscriptLine, TranscriptSegment


def _seg(start, score, text):
    return TranscriptSegment(start, start + 30, text, [TranscriptLine(text, start, 30)], score)


CANDIDATES = [_seg(0, 0.9, "keyword heavy but dull"), _seg(60, 0.5, "great hook"), _seg(120, 0.0, "off topic")]


def _gemini_answering(text):
    client = MagicMock()
    client.return_value.models.generate_content.return_value.text = text
    return patch.object(gm.genai, "Client", client)


def test_uses_geminis_choice():
    with _gemini_answering('{"choice": 2}') as client:
        assert gm.choose_segment(CANDIDATES, "t", "m", "k").text == "great hook"
    prompt = client.return_value.models.generate_content.call_args.kwargs["contents"]
    assert "off topic" not in prompt  # zero-score windows aren't offered


def test_falls_back_to_best_keyword_score_on_bad_answers():
    for answer in ['{"choice": 7}', "not json", '{"other": 1}']:
        with _gemini_answering(answer):
            assert gm.choose_segment(CANDIDATES, "t", "m", "k").text == "keyword heavy but dull"


def test_falls_back_when_gemini_errors():
    with patch.object(gm.genai, "Client", side_effect=RuntimeError("quota")):
        assert gm.choose_segment(CANDIDATES, "t", "m", "k").score == 0.9


def test_single_candidate_skips_gemini():
    with patch.object(gm.genai, "Client") as client:
        assert gm.choose_segment([CANDIDATES[1]], "t", "m", "k").text == "great hook"
    client.assert_not_called()


def _server_error():
    from google.genai import errors

    return errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def test_metadata_retries_gemini_overload_then_succeeds():
    client = MagicMock()
    ok = MagicMock(text='{"title": "T", "description": "D", "hashtags": ["a"]}')
    client.return_value.models.generate_content.side_effect = [_server_error(), _server_error(), ok]
    with patch.object(gm.genai, "Client", client), patch.object(gm.time, "sleep") as sleep:
        meta = gm.generate_metadata("topic", "text", "m", "k")
    assert meta.title == "T"
    assert sleep.call_count == 2


def test_metadata_gives_up_after_retries():
    import pytest

    from content_engine.errors import MetadataGenerationError

    client = MagicMock()
    client.return_value.models.generate_content.side_effect = _server_error()
    with patch.object(gm.genai, "Client", client), patch.object(gm.time, "sleep"):
        with pytest.raises(MetadataGenerationError, match="after 4 attempts"):
            gm.generate_metadata("topic", "text", "m", "k")
