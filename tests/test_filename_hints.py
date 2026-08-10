from pathlib import Path

from music_app.library.filename_hints import parse_filename_hints


def test_parses_track_artist_title_without_overreaching() -> None:
    tags = parse_filename_hints(Path("03 - Kendrick Lamar - Money Trees.flac"))
    assert tags.track_number == "3"
    assert tags.artist == "Kendrick Lamar"
    assert tags.title == "Money Trees"


def test_plain_filename_becomes_title_only() -> None:
    tags = parse_filename_hints(Path("Money Trees.mp3"))
    assert tags.artist is None
    assert tags.title == "Money Trees"


def test_two_part_name_is_artist_and_title() -> None:
    tags = parse_filename_hints(Path("Daft Punk - One More Time.flac"))
    assert tags.artist == "Daft Punk"
    assert tags.title == "One More Time"
