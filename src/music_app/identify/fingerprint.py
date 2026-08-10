from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Fingerprint:
    duration_s: float
    fingerprint: str


class FingerprintError(RuntimeError):
    pass


def fingerprint_file(
    path: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
    executable: str = "fpcalc",
    timeout_s: float = 30.0,
) -> Fingerprint:
    try:
        completed = runner(
            [executable, "-json", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FingerprintError(f"{executable} was not found; install Chromaprint/fpcalc") from exc
    except subprocess.TimeoutExpired as exc:
        raise FingerprintError(f"{executable} timed out while fingerprinting {path.name}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown fpcalc error").strip()
        raise FingerprintError(f"fpcalc failed for {path.name}: {detail}")

    try:
        payload = json.loads(completed.stdout)
        duration = float(payload["duration"])
        fingerprint = str(payload["fingerprint"]).strip()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise FingerprintError(f"fpcalc returned invalid JSON for {path.name}") from exc

    if not fingerprint:
        raise FingerprintError(f"fpcalc returned an empty fingerprint for {path.name}")
    return Fingerprint(duration_s=duration, fingerprint=fingerprint)
