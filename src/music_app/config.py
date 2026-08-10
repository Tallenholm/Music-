from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_config_dir


@dataclass(frozen=True, slots=True)
class AppConfig:
    acoustid_client_key: str = ""
    enable_acoustid: bool = False
    enable_itunes: bool = True
    enable_ai: bool = False
    preselect_confidence: float = 0.95
    rename_template: str = "{artist} - {title}"

    @classmethod
    def config_dir(cls) -> Path:
        override = os.environ.get("MUSIC_APP_CONFIG_DIR")
        if override:
            return Path(override)
        return Path(user_config_dir("Music-", "Tallenholm"))

    @classmethod
    def config_path(cls) -> Path:
        return cls.config_dir() / "config.json"

    @classmethod
    def load(cls) -> "AppConfig":
        path = cls.config_path()
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(payload, dict):
            return cls()
        allowed = {
            "acoustid_client_key",
            "enable_acoustid",
            "enable_itunes",
            "enable_ai",
            "preselect_confidence",
            "rename_template",
        }
        values = {key: payload[key] for key in allowed if key in payload}
        try:
            return cls(**values)
        except (TypeError, ValueError):
            return cls()

    def save(self) -> None:
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)
