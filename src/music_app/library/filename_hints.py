from __future__ import annotations

import re
from pathlib import Path

from music_app.domain import TrackTags

_TRACK_PREFIX = re.compile(r"^\s*(\d{1,3})\s*[-._)]\s*(.+)$")


def parse_filename_hints(path: Path) -> TrackTags:
    stem = Path(path).stem.strip()
    track_number: str | None = None
    remainder = stem

    match = _TRACK_PREFIX.match(stem)
    if match:
        track_number = str(int(match.group(1)))
        remainder = match.group(2).strip()

    parts = [part.strip() for part in remainder.split(" - ") if part.strip()]
    if len(parts) >= 2:
        artist = parts[0]
        title = " - ".join(parts[1:])
        return TrackTags(title=title, artist=artist, track_number=track_number)

    return TrackTags(title=remainder or None, track_number=track_number)
