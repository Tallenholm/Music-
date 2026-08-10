import os

import pytest

from music_app.identify.itunes import ITunesClient
from music_app.identify.matching import normalize_text


@pytest.mark.skipif(
    os.environ.get("MUSIC_LIVE_ITUNES") != "1",
    reason="set MUSIC_LIVE_ITUNES=1 to run the live Apple catalog smoke test",
)
def test_live_itunes_search_returns_known_song() -> None:
    results = ITunesClient(min_interval_s=0.0).search("Jack Johnson", "Upside Down")

    assert any(
        normalize_text(item.artist) == "jack johnson"
        and normalize_text(item.title) == "upside down"
        for item in results
    )
