from pathlib import Path

from music_app.domain import AIEnrichment, Candidate, TrackInput, TrackTags
from music_app.identify.pipeline import AnalysisPipeline


class StaticCatalog:
    def __init__(self, candidates):
        self.candidates = list(candidates)

    def search(self, artist, title):
        return list(self.candidates)


class BrokenCatalog:
    def search(self, artist, title):
        raise RuntimeError("catalog unavailable")


class StaticAI:
    def analyze(self, path):
        return AIEnrichment(genres=(("hip-hop", 0.91),), moods=(("energetic", 0.72),))


def test_pipeline_keeps_working_when_one_provider_fails() -> None:
    track = TrackInput(
        path=Path("Kendrick Lamar - Money Trees.mp3"),
        tags=TrackTags(artist="Kendrick Lamar", title="Money Trees"),
        duration_s=386.0,
    )
    candidate = Candidate(
        source="catalog",
        source_id="1",
        artist="Kendrick Lamar",
        title="Money Trees",
        album="good kid, m.A.A.d city",
        duration_s=386.2,
        source_confidence=1.0,
    )
    pipeline = AnalysisPipeline(catalogs=[BrokenCatalog(), StaticCatalog([candidate])])

    result = pipeline.analyze(track)

    assert result.match is not None
    assert result.match.candidate.title == "Money Trees"
    assert result.confidence_band == "high"
    assert result.preselected is True
    assert any("catalog unavailable" in error for error in result.errors)


def test_ai_enrichment_only_adds_non_identity_metadata() -> None:
    track = TrackInput(
        path=Path("song.mp3"),
        tags=TrackTags(artist="Existing Artist", title="Existing Title"),
    )
    pipeline = AnalysisPipeline(catalogs=[], ai_analyzer=StaticAI())

    result = pipeline.analyze(track)

    assert result.proposed_tags.artist is None
    assert result.proposed_tags.title is None
    assert result.proposed_tags.genre == "hip-hop"
    assert result.ai is not None


def test_low_confidence_result_is_not_preselected() -> None:
    track = TrackInput(
        path=Path("song.mp3"),
        tags=TrackTags(artist="Artist", title="Song"),
        duration_s=200.0,
    )
    candidate = Candidate(
        source="catalog",
        source_id="2",
        artist="Different Artist",
        title="Song",
        duration_s=200.0,
    )
    result = AnalysisPipeline(catalogs=[StaticCatalog([candidate])]).analyze(track)

    assert result.match is not None
    assert result.match.confidence < 0.85
    assert result.confidence_band == "low"
    assert result.preselected is False
