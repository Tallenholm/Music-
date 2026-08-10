from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from music_app.domain import ProposedChange


class TagWriter(Protocol):
    def write_fields(self, path: Path, values: dict[str, str | None]) -> None: ...


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    operation_id: str
    timestamp: str
    path: Path
    changes: tuple[ProposedChange, ...]
    undone: bool = False


class HistoryStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / "history.json"

    def record(self, path: Path, changes: tuple[ProposedChange, ...]) -> HistoryEntry:
        self.root.mkdir(parents=True, exist_ok=True)
        entry = HistoryEntry(
            operation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            path=Path(path).resolve(),
            changes=tuple(changes),
        )
        entries = self._load_raw()
        entries.append(self._serialize(entry))
        self._save_raw(entries)
        return entry

    def undo_last(self, writer: TagWriter) -> HistoryEntry | None:
        entries = self._load_raw()
        for index in range(len(entries) - 1, -1, -1):
            raw = entries[index]
            if raw.get("undone"):
                continue
            entry = self._deserialize(raw)
            restore = {change.field: change.old for change in entry.changes}
            writer.write_fields(entry.path, restore)
            raw["undone"] = True
            entries[index] = raw
            self._save_raw(entries)
            return HistoryEntry(
                operation_id=entry.operation_id,
                timestamp=entry.timestamp,
                path=entry.path,
                changes=entry.changes,
                undone=True,
            )
        return None

    def _load_raw(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return payload if isinstance(payload, list) else []

    def _save_raw(self, entries: list[dict[str, object]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="history-", suffix=".json", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entries, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _serialize(entry: HistoryEntry) -> dict[str, object]:
        return {
            "operation_id": entry.operation_id,
            "timestamp": entry.timestamp,
            "path": str(entry.path),
            "changes": [
                {"field": change.field, "old": change.old, "new": change.new}
                for change in entry.changes
            ],
            "undone": entry.undone,
        }

    @staticmethod
    def _deserialize(raw: dict[str, object]) -> HistoryEntry:
        changes = tuple(
            ProposedChange(
                field=str(item["field"]),
                old=item.get("old"),
                new=item.get("new"),
            )
            for item in raw.get("changes", [])
            if isinstance(item, dict) and "field" in item
        )
        return HistoryEntry(
            operation_id=str(raw["operation_id"]),
            timestamp=str(raw["timestamp"]),
            path=Path(str(raw["path"])),
            changes=changes,
            undone=bool(raw.get("undone", False)),
        )
