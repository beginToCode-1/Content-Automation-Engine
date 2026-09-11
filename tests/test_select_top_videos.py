import pytest

from content_engine.errors import SearchFailedError
from content_engine.models import VideoCandidate
from content_engine.search.youtube_search import select_top


def _candidate(video_id, title, duration_s=200, view_count=100):
    return VideoCandidate(
        video_id=video_id,
        title=title,
        description="",
        channel="chan",
        published_at="2026-01-01T00:00:00Z",
        duration_s=duration_s,
        view_count=view_count,
    )


def test_select_top_returns_requested_count_ranked_by_relevance():
    candidates = [
        _candidate("a", "stoic philosophy deep dive"),
        _candidate("b", "cooking pasta recipes"),
        _candidate("c", "stoic philosophy and marcus aurelius"),
        _candidate("d", "car repair tutorial"),
    ]

    top = select_top(candidates, "stoic philosophy", count=2)

    assert len(top) == 2
    assert {c.video_id for c in top} == {"a", "c"}


def test_select_top_returns_fewer_than_count_when_not_enough_eligible():
    candidates = [_candidate("a", "stoic philosophy"), _candidate("b", "stoicism basics", duration_s=10)]

    top = select_top(candidates, "stoic philosophy", count=5, min_duration_s=90)

    assert len(top) == 1
    assert top[0].video_id == "a"


def test_select_top_raises_when_zero_eligible():
    candidates = [_candidate("a", "stoic philosophy", duration_s=5)]

    with pytest.raises(SearchFailedError):
        select_top(candidates, "stoic philosophy", count=3, min_duration_s=90)
