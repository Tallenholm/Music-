from music_app.identify.acoustid import AcoustIDClient, AcoustIDConfigError
from music_app.identify.fingerprint import Fingerprint


class ResponseFixture:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class RecordingTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, *, data, timeout):
        self.calls.append((url, data, timeout))
        return ResponseFixture(self.payload)


def test_acoustid_maps_recording_to_candidate() -> None:
    payload = {
        "status": "ok",
        "results": [
            {
                "score": 0.98,
                "id": "acoustid-1",
                "recordings": [
                    {
                        "id": "recording-1",
                        "title": "Money Trees",
                        "artists": [{"name": "Kendrick Lamar"}],
                        "releases": [{"title": "good kid, m.A.A.d city"}],
                    }
                ],
            }
        ],
    }
    transport = RecordingTransport(payload)
    client = AcoustIDClient("client-key", transport=transport, sleeper=lambda _: None)
    result = client.lookup(Fingerprint(386.0, "abc"))
    assert len(result) == 1
    assert result[0].source == "acoustid"
    assert result[0].source_id == "recording-1"
    assert result[0].artist == "Kendrick Lamar"
    assert result[0].title == "Money Trees"
    assert result[0].album == "good kid, m.A.A.d city"
    assert result[0].source_confidence == 0.98


def test_acoustid_requires_user_key() -> None:
    try:
        AcoustIDClient("", transport=RecordingTransport({}))
    except AcoustIDConfigError as exc:
        assert "client key" in str(exc).lower()
    else:
        raise AssertionError("missing key should fail")
