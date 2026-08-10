from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TrackTags:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: str | None = None
    disc_number: str | None = None
    date: str | None = None
    genre: str | None = None
    comment: str | None = None
    isrc: str | None = None


@dataclass(frozen=True, slots=True)
class TrackInput:
    path: Path
    tags: TrackTags = field(default_factory=TrackTags)
    duration_s: float | None = None
    filename_hints: TrackTags = field(default_factory=TrackTags)


@dataclass(frozen=True, slots=True)
class Candidate:
    source: str
    source_id: str
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    duration_s: float | None = None
    track_number: str | None = None
    disc_number: str | None = None
    date: str | None = None
    genre: str | None = None
    comment: str | None = None
    isrc: str | None = None
    source_confidence: float | None = None


@dataclass(frozen=True, slots=True)
class MatchResult:
    candidate: Candidate
    confidence: float
    alternatives: tuple[Candidate, ...] = ()
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProposedChange:
    field: str
    old: str | None
    new: str | None


@dataclass(frozen=True, slots=True)
class AIEnrichment:
    genres: tuple[tuple[str, float], ...] = ()
    moods: tuple[tuple[str, float], ...] = ()
    available: bool = True
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    track: TrackInput
    match: MatchResult | None = None
    proposed_tags: TrackTags = field(default_factory=TrackTags)
    changes: tuple[ProposedChange, ...] = ()
    ai: AIEnrichment | None = None
    errors: tuple[str, ...] = ()
    confidence_band: str = "low"
    preselected: bool = False
