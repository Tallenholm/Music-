from pathlib import Path

from music_app.domain import Candidate, TrackInput, TrackTags
from music_app.identify.matching import choose_match, score_candidate


def test_exact_artist_title_and_close_duration_scores_high() -> None:
    track = TrackInput(
        path=Path("x.mp3"),
        tags=TrackTags(artist="Kendrick Lamar", title="Money Trees"),
        duration_s=386.0,
    )
    candidate = Candidate(
        source="itunes",
        source_id="1",
        artist="Kendrick Lamar",
        title="Money Trees",
        duration_s=386.4,
        source_confidence=1.0,
    )
    assert score_candidate(track, candidate) >= 0.95


def test_bad_artist_cannot_win_on_duration_alone() -> None:
    track = TrackInput(
        path=Path("x.mp3"),
        tags=TrackTags(artist="Kendrick Lamar", title="Money Trees"),
        duration_s=386.0,
    )
    wrong = Candidate(
        source="itunes",
        source_id="2",
        artist="Different Artist",
        title="Money Trees",
        duration_s=386.0,
        source_confidence=1.0,
    )
    assert score_candidate(track, wrong) < 0.85


def test_filename_hints_fill_missing_embedded_tags() -> None:
    track = TrackInput(
        path=Path("x.mp3"),
        filename_hints=TrackTags(artist="Daft Punk", title="One More Time"),
        duration_s=320.0,
    )
    candidate = Candidate(
        source="itunes",
        source_id="3",
        artist="Daft Punk",
        title="One More Time",
        duration_s=320.0,
    )
    assert score_candidate(track, candidate) >= 0.95


def test_choose_match_returns_highest_candidate() -> None:
    track = TrackInput(
        path=Path("x.mp3"),
        tags=TrackTags(artist="Artist", title="Song"),
        duration_s=100.0,
    )
    good = Candidate(
        source="itunes", source_id="good", artist="Artist", title="Song", duration_s=100.0
    )
    bad = Candidate(
        source="itunes", source_id="bad", artist="Other", title="Song", duration_s=100.0
    )
    result = choose_match(track, [bad, good])
    assert result is not None
    assert result.candidate.source_id == "good"
    assert result.confidence > 0.9
