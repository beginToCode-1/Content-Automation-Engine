from content_engine.errors import NoTranscriptAvailableError
from content_engine.models import TranscriptLine, TranscriptSegment
from content_engine.scoring import relevance_scores


def _total_duration(transcript: list[TranscriptLine]) -> float:
    return transcript[-1].start + transcript[-1].duration


def _build_windows(
    transcript: list[TranscriptLine],
    total_duration: float,
    min_s: float,
    max_s: float,
    stride_s: float,
) -> list[tuple[float, float, list[TranscriptLine]]]:
    windows: list[tuple[float, float, list[TranscriptLine]]] = []
    t = 0.0
    while t + min_s <= total_duration:
        window_end = min(t + max_s, total_duration)
        window_lines = [ln for ln in transcript if ln.start >= t and ln.start + ln.duration <= window_end]
        if window_lines and (window_lines[-1].start + window_lines[-1].duration - window_lines[0].start) >= min_s:
            windows.append((window_lines[0].start, window_lines[-1].start + window_lines[-1].duration, window_lines))
        t += stride_s
    return windows


def select_best_segment(
    transcript: list[TranscriptLine],
    topic: str,
    min_s: float = 30.0,
    max_s: float = 60.0,
    stride_s: float = 5.0,
) -> TranscriptSegment:
    if not transcript:
        raise NoTranscriptAvailableError("Cannot select a segment from an empty transcript")

    total_duration = _total_duration(transcript)
    if total_duration < min_s:
        raise NoTranscriptAvailableError(
            f"Transcript is only {total_duration:.1f}s long, shorter than the minimum segment length {min_s}s"
        )

    windows = _build_windows(transcript, total_duration, min_s, max_s, stride_s)
    if not windows:
        raise NoTranscriptAvailableError(
            f"Could not find any {min_s}-{max_s}s window with transcript coverage"
        )

    documents = [" ".join(ln.text for ln in lines) for _, _, lines in windows]
    scores = relevance_scores(topic, documents)

    best_index = max(range(len(windows)), key=lambda i: scores[i])
    start_s, end_s, lines = windows[best_index]
    return TranscriptSegment(
        start_s=start_s,
        end_s=end_s,
        text=" ".join(ln.text for ln in lines),
        lines=lines,
        score=scores[best_index],
    )


def select_top_segments(
    transcript: list[TranscriptLine],
    topic: str,
    count: int,
    min_s: float = 30.0,
    max_s: float = 60.0,
    stride_s: float = 5.0,
) -> list[TranscriptSegment]:
    """Same window-building and scoring as select_best_segment, but greedily
    accepts the highest-scoring windows whose [start_s, end_s) interval does not
    overlap any already-accepted window, until `count` are accepted or candidates
    run out. Returns fewer than `count` if the transcript doesn't contain enough
    non-overlapping high-scoring windows. Result is ordered by start_s (chronological)."""
    if not transcript:
        raise NoTranscriptAvailableError("Cannot select a segment from an empty transcript")

    total_duration = _total_duration(transcript)
    if total_duration < min_s:
        raise NoTranscriptAvailableError(
            f"Transcript is only {total_duration:.1f}s long, shorter than the minimum segment length {min_s}s"
        )

    windows = _build_windows(transcript, total_duration, min_s, max_s, stride_s)
    if not windows:
        raise NoTranscriptAvailableError(
            f"Could not find any {min_s}-{max_s}s window with transcript coverage"
        )

    documents = [" ".join(ln.text for ln in lines) for _, _, lines in windows]
    scores = relevance_scores(topic, documents)

    order = sorted(range(len(windows)), key=lambda i: scores[i], reverse=True)
    accepted_intervals: list[tuple[float, float]] = []
    selected: list[TranscriptSegment] = []

    for i in order:
        start_s, end_s, lines = windows[i]
        overlaps = any(start_s < acc_end and end_s > acc_start for acc_start, acc_end in accepted_intervals)
        if overlaps:
            continue
        accepted_intervals.append((start_s, end_s))
        selected.append(
            TranscriptSegment(
                start_s=start_s,
                end_s=end_s,
                text=" ".join(ln.text for ln in lines),
                lines=lines,
                score=scores[i],
            )
        )
        if len(selected) >= count:
            break

    selected.sort(key=lambda s: s.start_s)
    return selected
