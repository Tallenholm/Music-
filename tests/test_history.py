import json
from pathlib import Path

from music_app.domain import ProposedChange
from music_app.library.history import HistoryStore
from music_app.library.tags import MutagenTagIO


def test_record_and_undo_restore_real_mp3_fields(real_mp3: Path, tmp_path: Path) -> None:
    writer = MutagenTagIO()
    writer.write_fields(
        real_mp3,
        {"title": "Old", "artist": "Keep Artist", "genre": "Rock"},
    )
    changes = (
        ProposedChange("title", "Old", "New"),
        ProposedChange("genre", "Rock", "Electronic"),
    )
    store = HistoryStore(tmp_path / "history")
    entry = store.record(real_mp3, changes)
    writer.write_fields(real_mp3, {"title": "New", "genre": "Electronic"})

    undone = store.undo_last(writer)
    reread = writer.read_track(real_mp3)

    assert undone is not None
    assert undone.operation_id == entry.operation_id
    assert reread.tags.title == "Old"
    assert reread.tags.genre == "Rock"
    assert reread.tags.artist == "Keep Artist"
    payload = json.loads((tmp_path / "history" / "history.json").read_text(encoding="utf-8"))
    assert payload[0]["undone"] is True


def test_history_serialization_never_contains_api_keys(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    store.record(tmp_path / "song.mp3", (ProposedChange("title", "a", "b"),))
    serialized = (tmp_path / "history.json").read_text(encoding="utf-8").casefold()
    assert "acoustid" not in serialized
    assert "api_key" not in serialized
