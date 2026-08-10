from pathlib import Path

from music_app.library.scanner import discover_audio_files


def test_discovers_supported_files_recursively(tmp_path: Path) -> None:
    album = tmp_path / "Album"
    album.mkdir()
    mp3 = album / "01 - Song.mp3"
    flac = album / "02 - Song.flac"
    ignored = album / "cover.jpg"
    mp3.write_bytes(b"")
    flac.write_bytes(b"")
    ignored.write_bytes(b"")

    assert discover_audio_files([tmp_path]) == [mp3, flac]


def test_deduplicates_overlapping_inputs(tmp_path: Path) -> None:
    song = tmp_path / "song.MP3"
    song.write_bytes(b"")
    assert discover_audio_files([tmp_path, song]) == [song]
