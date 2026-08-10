from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from music_app.domain import Candidate, MatchResult, TrackInput

_WEIGHTS = {
    "artist": 0.25,
    "title": 0.25,
    "duration": 0.20,
    "album": 0.10,
    "isrc": 0.10,
    "provider": 0.10,
}


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.casefold().strip()
    lowered = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return " ".join(lowered.split())


def _text_similarity(left: str | None, right: str | None) -> float | None:
    a = normalize_text(left)
    b = normalize_text(right)
    if not a or not b:
        return None
    return SequenceMatcher(None, a, b).ratio()


def _duration_similarity(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    diff = abs(left - right)
    if diff <= 1.0:
        return 1.0
    if diff >= 15.0:
        return 0.0
    return 1.0 - ((diff - 1.0) / 14.0)


def _preferred(value: str | None, fallback: str | None) -> str | None:
    return value if value and value.strip() else fallback


def score_candidate(track: TrackInput, candidate: Candidate) -> float:
    artist = _preferred(track.tags.artist, track.filename_hints.artist)
    title = _preferred(track.tags.title, track.filename_hints.title)
    album = _preferred(track.tags.album, track.filename_hints.album)
    isrc = _preferred(track.tags.isrc, track.filename_hints.isrc)

    components: list[tuple[float, float]] = []

    artist_score = _text_similarity(artist, candidate.artist)
    if artist_score is not None:
        components.append((_WEIGHTS["artist"], artist_score))

    title_score = _text_similarity(title, candidate.title)
    if title_score is not None:
        components.append((_WEIGHTS["title"], title_score))

    duration_score = _duration_similarity(track.duration_s, candidate.duration_s)
    if duration_score is not None:
        components.append((_WEIGHTS["duration"], duration_score))

    album_score = _text_similarity(album, candidate.album)
    if album_score is not None:
        components.append((_WEIGHTS["album"], album_score))

    if isrc and candidate.isrc:
        components.append((_WEIGHTS["isrc"], float(normalize_text(isrc) == normalize_text(candidate.isrc))))

    if candidate.source_confidence is not None:
        components.append((_WEIGHTS["provider"], max(0.0, min(1.0, candidate.source_confidence))))

    if not components:
        return 0.0

    total_weight = sum(weight for weight, _ in components)
    return max(0.0, min(1.0, sum(weight * score for weight, score in components) / total_weight))


def choose_match(track: TrackInput, candidates: Sequence[Candidate]) -> MatchResult | None:
    if not candidates:
        return None

    scored = [(candidate, score_candidate(track, candidate)) for candidate in candidates]
    scored.sort(key=lambda item: item[1], reverse=True)
    winner, confidence = scored[0]

    agreeing_sources = {
        candidate.source
        for candidate, _ in scored
        if normalize_text(candidate.artist) == normalize_text(winner.artist)
        and normalize_text(candidate.title) == normalize_text(winner.title)
        and candidate.source != winner.source
    }
    if agreeing_sources:
        confidence = min(1.0, confidence + 0.03)

    alternatives = tuple(candidate for candidate, _ in scored[1:4])
    return MatchResult(candidate=winner, confidence=confidence, alternatives=alternatives)
