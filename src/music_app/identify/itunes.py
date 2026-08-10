from __future__ import annotations

import time
from typing import Any

import httpx

from music_app.domain import Candidate


class ITunesClient:
    def __init__(
        self,
        *,
        transport: Any | None = None,
        country: str = "US",
        sleeper=time.sleep,
        clock=time.monotonic,
        min_interval_s: float = 3.1,
    ) -> None:
        self.transport = transport or httpx.Client()
        self.country = country
        self.sleeper = sleeper
        self.clock = clock
        self.min_interval_s = min_interval_s
        self._last_request_at: float | None = None
        self._cache: dict[tuple[str, str], list[Candidate]] = {}

    def _rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.min_interval_s - (self.clock() - self._last_request_at)
        if remaining > 0:
            self.sleeper(remaining)

    def search(self, artist: str | None, title: str) -> list[Candidate]:
        key = ((artist or "").strip().casefold(), title.strip().casefold())
        if key in self._cache:
            return list(self._cache[key])

        term = " ".join(part for part in ((artist or "").strip(), title.strip()) if part)
        self._rate_limit()
        response = self.transport.get(
            "https://itunes.apple.com/search",
            params={
                "term": term,
                "country": self.country,
                "media": "music",
                "entity": "song",
                "limit": 25,
            },
            timeout=10.0,
        )
        self._last_request_at = self.clock()
        response.raise_for_status()
        payload = response.json()
        candidates: list[Candidate] = []
        for item in payload.get("results", []):
            if item.get("kind") != "song":
                continue
            release_date = str(item.get("releaseDate") or "")
            candidates.append(
                Candidate(
                    source="itunes",
                    source_id=str(item.get("trackId") or ""),
                    title=item.get("trackName"),
                    artist=item.get("artistName"),
                    album=item.get("collectionName"),
                    album_artist=item.get("collectionArtistName") or item.get("artistName"),
                    duration_s=_millis_to_seconds(item.get("trackTimeMillis")),
                    track_number=_optional_int_string(item.get("trackNumber")),
                    disc_number=_optional_int_string(item.get("discNumber")),
                    date=release_date[:4] if len(release_date) >= 4 else None,
                    genre=item.get("primaryGenreName"),
                    source_confidence=1.0,
                )
            )
        self._cache[key] = candidates
        return list(candidates)


def _millis_to_seconds(value: object) -> float | None:
    try:
        return float(value) / 1000.0 if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int_string(value: object) -> str | None:
    try:
        return str(int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
