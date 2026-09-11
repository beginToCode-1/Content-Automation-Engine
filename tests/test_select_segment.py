import json
from pathlib import Path

from content_engine.models import TranscriptLine
from content_engine.transcript.select_segment import select_best_segment

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_transcript.json"


def _load_transcript() -> list[TranscriptLine]:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [TranscriptLine(**item) for item in raw]


def test_select_best_segment_picks_topically_relevant_window():
    transcript = _load_transcript()
    segment = select_best_segment(transcript, topic="stoic philosophy")

    assert "stoic" in segment.text.lower()
    assert "baking bread" not in segment.text.lower()
    assert "flour" not in segment.text.lower()
    assert segment.end_s - segment.start_s >= 30


def test_select_best_segment_respects_max_length():
    transcript = _load_transcript()
    segment = select_best_segment(transcript, topic="stoic philosophy")

    assert (segment.end_s - segment.start_s) <= 60 + 1e-6
