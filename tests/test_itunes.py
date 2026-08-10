from music_app.identify.itunes import ITunesClient


class ResponseFixture:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class RecordingTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return ResponseFixture(self.payload)


def test_itunes_maps_song_result() -> None:
    payload = {
        "resultCount": 1,
        "results": [
            {
                "kind": "song",
                "trackId": 42,
                "trackName": "One More Time",
                "artistName": "Daft Punk",
                "collectionName": "Discovery",
                "trackTimeMillis": 320000,
                "trackNumber": 1,
                "discNumber": 1,
                "releaseDate": "2001-03-12T08:00:00Z",
                "primaryGenreName": "Electronic",
            }
        ],
    }
    client = ITunesClient(
        transport=RecordingTransport(payload), sleeper=lambda _: None, clock=lambda: 0.0
    )
    result = client.search("Daft Punk", "One More Time")
    assert len(result) == 1
    candidate = result[0]
    assert candidate.source == "itunes"
    assert candidate.source_id == "42"
    assert candidate.duration_s == 320.0
    assert candidate.date == "2001"
    assert candidate.genre == "Electronic"


def test_itunes_reuses_identical_query_cache() -> None:
    transport = RecordingTransport({"resultCount": 0, "results": []})
    client = ITunesClient(transport=transport, sleeper=lambda _: None, clock=lambda: 0.0)
    assert client.search("Artist", "Song") == []
    assert client.search("Artist", "Song") == []
    assert len(transport.calls) == 1
