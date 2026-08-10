from __future__ import annotations

import time
from typing import Any

import httpx

from music_app.domain import Candidate
from music_app.identify.fingerprint import Fingerprint


class AcoustIDConfigError(ValueError):
    pass


class AcoustIDClient:
    def __init__(
        self,
        client_key: str,
        *,
        transport: Any | None = None,
        sleeper=time.sleep,
        clock=time.monotonic,
    ) -> None:
        if not client_key.strip():
            raise AcoustIDConfigError("An AcoustID client key is required")
        self.client_key = client_key.strip()
        self.transport = transport or httpx.Client()
        self.sleeper = sleeper
        self.clock = clock
        self._last_request_at: float | None = None

    def _rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = (1.0 / 3.0) - (self.clock() - self._last_request_at)
        if remaining > 0:
            self.sleeper(remaining)

    def lookup(self, fingerprint: Fingerprint) -> list[Candidate]:
        self._rate_limit()
        response = self.transport.post(
            "https://api.acoustid.org/v2/lookup",
            data={
                "client": self.client_key,
                "duration": int(round(fingerprint.duration_s)),
                "fingerprint": fingerprint.fingerprint,
                "format": "json",
                "meta": "recordings+releases+releasegroups+tracks",
            },
            timeout=10.0,
        )
        self._last_request_at = self.clock()
        response.raise_for_status()
        payload = response.json()
        candidates: list[Candidate] = []
        for result in payload.get("results", []):
            score = _safe_float(result.get("score"))
            recordings = result.get("recordings") or []
            for recording in recordings:
                artists = recording.get("artists") or []
                artist = ", ".join(
                    item.get("name", "").strip() for item in artists if item.get("name")
                ) or None
                releases = recording.get("releases") or []
                release = releases[0] if releases else {}
                candidates.append(
                    Candidate(
                        source="acoustid",
                        source_id=str(recording.get("id") or result.get("id") or ""),
                        title=recording.get("title"),
                        artist=artist,
                        album=release.get("title"),
                        source_confidence=score,
                    )
                )
        return candidates


def _safe_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
