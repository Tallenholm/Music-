from __future__ import annotations

from dataclasses import fields

from music_app.domain import ProposedChange, TrackTags

SUPPORTED_WRITE_FIELDS = frozenset(
    {
        "title",
        "artist",
        "album",
        "album_artist",
        "track_number",
        "disc_number",
        "date",
        "genre",
        "comment",
        "isrc",
    }
)


def _normalized(value: str | None) -> str:
    return " ".join(value.split()) if value else ""


def build_changes(current: TrackTags, proposed: TrackTags) -> tuple[ProposedChange, ...]:
    changes: list[ProposedChange] = []
    for item in fields(TrackTags):
        name = item.name
        if name not in SUPPORTED_WRITE_FIELDS:
            continue
        old = getattr(current, name)
        new = getattr(proposed, name)
        if new is None or not str(new).strip():
            continue
        if _normalized(old) == _normalized(new):
            continue
        changes.append(ProposedChange(field=name, old=old, new=str(new).strip()))
    return tuple(changes)


_EASY_FIELD_KEYS = {
    "title": "title",
    "artist": "artist",
    "album": "album",
    "album_artist": "albumartist",
    "track_number": "tracknumber",
    "disc_number": "discnumber",
    "date": "date",
    "genre": "genre",
    "comment": "comment",
    "isrc": "isrc",
}
_ID3_SUFFIXES = {".mp3", ".wav", ".aiff", ".aif"}


class MutagenTagIO:
    def __init__(self, *, easy_opener=None, raw_opener=None) -> None:
        if easy_opener is None or raw_opener is None:
            import mutagen
            from mutagen.easymp4 import EasyMP4Tags

            if "isrc" not in EasyMP4Tags.Get:
                EasyMP4Tags.RegisterFreeformKey("isrc", "ISRC")
            easy_opener = easy_opener or mutagen.File
            raw_opener = raw_opener or (lambda path: mutagen.File(path, easy=False))
        self.easy_opener = easy_opener
        self.raw_opener = raw_opener

    def read_track(self, path):
        from pathlib import Path
        from music_app.domain import TrackInput, TrackTags
        from music_app.library.filename_hints import parse_filename_hints

        path = Path(path)
        audio = self.easy_opener(path, easy=True)
        if audio is None:
            raise ValueError(f"Unsupported or unreadable audio file: {path}")
        tags = getattr(audio, "tags", None) or {}

        def first(key):
            value = tags.get(key)
            if isinstance(value, (list, tuple)):
                return str(value[0]) if value else None
            return str(value) if value is not None else None

        values = {field: first(key) for field, key in _EASY_FIELD_KEYS.items() if field != "comment"}
        comment = first("comment")
        if comment is None and path.suffix.lower() in _ID3_SUFFIXES:
            raw = self.raw_opener(path)
            raw_tags = getattr(raw, "tags", None)
            if raw_tags is not None and hasattr(raw_tags, "getall"):
                frames = raw_tags.getall("COMM")
                if frames:
                    text = getattr(frames[0], "text", None)
                    if text:
                        comment = str(text[0])
        values["comment"] = comment
        duration = getattr(getattr(audio, "info", None), "length", None)
        return TrackInput(
            path=path,
            tags=TrackTags(**values),
            duration_s=float(duration) if duration is not None else None,
            filename_hints=parse_filename_hints(path),
        )

    def write_fields(self, path, values):
        from pathlib import Path

        path = Path(path)
        unsupported = set(values) - SUPPORTED_WRITE_FIELDS
        if unsupported:
            raise ValueError(f"Unsupported tag fields: {', '.join(sorted(unsupported))}")

        audio = self.easy_opener(path, easy=True)
        if audio is None:
            raise ValueError(f"Unsupported or unreadable audio file: {path}")
        if getattr(audio, "tags", None) is None and hasattr(audio, "add_tags"):
            audio.add_tags()
        tags = audio.tags
        easy_changed = False

        for field, value in values.items():
            if field == "comment" and path.suffix.lower() in _ID3_SUFFIXES:
                continue
            key = _EASY_FIELD_KEYS[field]
            if value is None or not str(value).strip():
                if key in tags:
                    del tags[key]
                    easy_changed = True
            else:
                tags[key] = [str(value).strip()]
                easy_changed = True

        if easy_changed:
            audio.save()

        if "comment" in values and path.suffix.lower() in _ID3_SUFFIXES:
            self._write_id3_comment(path, values["comment"])

    def _write_id3_comment(self, path, value):
        from mutagen.id3 import COMM

        raw = self.raw_opener(path)
        if raw is None:
            raise ValueError(f"Unsupported or unreadable audio file: {path}")
        if getattr(raw, "tags", None) is None:
            raw.add_tags()
        raw.tags.delall("COMM")
        if value is not None and str(value).strip():
            raw.tags.add(COMM(encoding=3, lang="eng", desc="", text=[str(value).strip()]))
        raw.save()
