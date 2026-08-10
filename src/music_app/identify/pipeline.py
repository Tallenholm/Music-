from __future__ import annotations

from dataclasses import replace
from typing import Any

from music_app.domain import AnalysisResult, Candidate, TrackInput, TrackTags
from music_app.identify.matching import choose_match
from music_app.library.tags import build_changes


class AnalysisPipeline:
    def __init__(
        self,
        *,
        catalogs: list[Any] | tuple[Any, ...] = (),
        fingerprinter=None,
        acoustid_client=None,
        ai_analyzer=None,
        preselect_confidence: float = 0.95,
    ) -> None:
        self.catalogs = tuple(catalogs)
        self.fingerprinter = fingerprinter
        self.acoustid_client = acoustid_client
        self.ai_analyzer = ai_analyzer
        self.preselect_confidence = preselect_confidence

    def analyze(self, track: TrackInput) -> AnalysisResult:
        candidates: list[Candidate] = []
        errors: list[str] = []

        if self.fingerprinter is not None and self.acoustid_client is not None:
            try:
                fingerprint = self.fingerprinter(track.path)
                candidates.extend(self.acoustid_client.lookup(fingerprint))
            except Exception as exc:  # provider boundary: degrade gracefully
                errors.append(f"fingerprint/AcoustID: {exc}")

        artist = _first_nonblank(track.tags.artist, track.filename_hints.artist)
        title = _first_nonblank(track.tags.title, track.filename_hints.title)
        if title:
            for catalog in self.catalogs:
                try:
                    candidates.extend(catalog.search(artist, title))
                except Exception as exc:  # provider boundary: degrade gracefully
                    errors.append(f"{type(catalog).__name__}: {exc}")

        match = choose_match(track, candidates)
        proposed = _tags_from_candidate(match.candidate) if match is not None else TrackTags()

        ai = None
        if self.ai_analyzer is not None:
            try:
                ai = self.ai_analyzer.analyze(track.path)
                if ai.available and ai.genres and not proposed.genre:
                    proposed = replace(proposed, genre=ai.genres[0][0])
                if ai.error:
                    errors.append(f"AI: {ai.error}")
            except Exception as exc:  # optional feature must not block identification
                errors.append(f"AI: {exc}")

        changes = build_changes(track.tags, proposed)
        confidence = match.confidence if match is not None else 0.0
        band = _confidence_band(confidence)
        preselected = match is not None and confidence >= self.preselect_confidence
        return AnalysisResult(
            track=track,
            match=match,
            proposed_tags=proposed,
            changes=changes,
            ai=ai,
            errors=tuple(errors),
            confidence_band=band,
            preselected=preselected,
        )


def _tags_from_candidate(candidate: Candidate) -> TrackTags:
    return TrackTags(
        title=candidate.title,
        artist=candidate.artist,
        album=candidate.album,
        album_artist=candidate.album_artist,
        track_number=candidate.track_number,
        disc_number=candidate.disc_number,
        date=candidate.date,
        genre=candidate.genre,
        comment=candidate.comment,
        isrc=candidate.isrc,
    )


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.95:
        return "high"
    if confidence >= 0.85:
        return "review"
    return "low"


def _first_nonblank(primary: str | None, secondary: str | None) -> str | None:
    if primary and primary.strip():
        return primary.strip()
    if secondary and secondary.strip():
        return secondary.strip()
    return None
