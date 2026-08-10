from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

SUPPORTED_EXTENSIONS = frozenset({".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus", ".wav", ".aiff", ".aif"})


def discover_audio_files(paths: Iterable[Path]) -> list[Path]:
    discovered: dict[str, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            candidates = (candidate for candidate in path.rglob("*") if candidate.is_file())
        elif path.is_file():
            candidates = (path,)
        else:
            continue

        for candidate in candidates:
            if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            resolved = candidate.resolve()
            discovered[str(resolved).casefold()] = candidate

    return sorted(discovered.values(), key=lambda item: str(item).casefold())
