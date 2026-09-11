import json
from pathlib import Path

from content_engine.models import TranscriptLine
from content_engine.transcript.select_segment import select_best_segment, select_top_segments

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_transcript.json"


def _load_transcript() -> list[TranscriptLine]:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [TranscriptLine(**item) for item in raw]


def test_select_top_segments_returns_non_overlapping_segments():
    # Note: this only asserts the function's actual guarantees (count, non-overlap,
    # topical relevance) - it does not demand zero contamination from an adjacent
    # off-topic line at a window boundary, since TF-IDF scoring can occasionally
    # prefer a slightly wider window with one bleed-over line over a narrower pure
    # one if it has more total matching terms. Same precedent as select_best_segment.
    transcript = _load_transcript()
    segments = select_top_segments(transcript, topic="stoic philosophy", count=2)

    assert len(segments) == 2
    a, b = segments
    assert a.end_s <= b.start_s or b.end_s <= a.start_s

    for segment in segments:
        assert "stoic" in segment.text.lower()


def test_select_top_segments_are_chronologically_ordered():
    transcript = _load_transcript()
    segments = select_top_segments(transcript, topic="stoic philosophy", count=2)

    starts = [s.start_s for s in segments]
    assert starts == sorted(starts)


def test_select_top_segments_returns_fewer_when_not_enough_non_overlapping_windows():
    transcript = _load_transcript()
    segments = select_top_segments(transcript, topic="stoic philosophy", count=10)

    assert 0 < len(segments) < 10


def test_select_best_segment_unaffected_by_shared_window_builder_extraction():
    transcript = _load_transcript()
    segment = select_best_segment(transcript, topic="stoic philosophy")

    assert "stoic" in segment.text.lower()
    assert segment.end_s - segment.start_s >= 30
