import subprocess
from pathlib import Path

import mutagen
from mutagen.id3 import COMM

from music_app.domain import TrackTags
from music_app.library.tags import MutagenTagIO


def _make_real_mp3(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-q:a",
            "9",
            str(path),
        ],
        check=True,
    )


def _seed_real_tags(path: Path) -> None:
    easy = mutagen.File(path, easy=True)
    assert easy is not None
    if easy.tags is None:
        easy.add_tags()
    easy["title"] = ["Old Title"]
    easy["artist"] = ["Artist"]
    easy["album"] = ["Album"]
    easy["tracknumber"] = ["1/10"]
    easy["date"] = ["2024"]
    easy["genre"] = ["Rock"]
    easy["isrc"] = ["USABC1234567"]
    easy.save()

    raw = mutagen.File(path, easy=False)
    assert raw is not None
    if raw.tags is None:
        raw.add_tags()
    raw.tags.delall("COMM")
    raw.tags.add(COMM(encoding=3, lang="eng", desc="", text=["original comment"]))
    raw.save()


def test_mutagen_tag_io_reads_real_mp3_fields(tmp_path: Path) -> None:
    path = tmp_path / "Artist - Old Title.mp3"
    _make_real_mp3(path)
    _seed_real_tags(path)

    track = MutagenTagIO().read_track(path)

    assert track.tags == TrackTags(
        title="Old Title",
        artist="Artist",
        album="Album",
        album_artist=None,
        track_number="1/10",
        disc_number=None,
        date="2024",
        genre="Rock",
        comment="original comment",
        isrc="USABC1234567",
    )
    assert track.duration_s is not None
    assert 0.9 <= track.duration_s <= 1.2


def test_mutagen_tag_io_persists_real_mp3_changes(tmp_path: Path) -> None:
    path = tmp_path / "song.mp3"
    _make_real_mp3(path)
    _seed_real_tags(path)

    MutagenTagIO().write_fields(
        path,
        {
            "title": "New Title",
            "genre": None,
            "comment": "checked by Music-",
        },
    )

    easy = mutagen.File(path, easy=True)
    assert easy is not None
    assert easy["title"] == ["New Title"]
    assert "genre" not in easy

    raw = mutagen.File(path, easy=False)
    assert raw is not None
    frames = raw.tags.getall("COMM")
    assert len(frames) == 1
    assert str(frames[0].text[0]) == "checked by Music-"
