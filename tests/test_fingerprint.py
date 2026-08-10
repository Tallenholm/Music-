import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from music_app.identify.fingerprint import Fingerprint, FingerprintError, fingerprint_file


def test_parses_fpcalc_json(tmp_path: Path) -> None:
    song = tmp_path / "song.flac"
    song.write_bytes(b"")

    def runner(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"duration": 123.4, "fingerprint": "abc"}),
            stderr="",
        )

    assert fingerprint_file(song, runner=runner) == Fingerprint(duration_s=123.4, fingerprint="abc")


def test_nonzero_fpcalc_exit_is_user_readable(tmp_path: Path) -> None:
    song = tmp_path / "song.flac"
    song.write_bytes(b"")

    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="decode failed")

    with pytest.raises(FingerprintError, match="decode failed"):
        fingerprint_file(song, runner=runner)


def test_missing_fpcalc_is_user_readable(tmp_path: Path) -> None:
    song = tmp_path / "song.flac"
    song.write_bytes(b"")

    def runner(*args, **kwargs):
        raise FileNotFoundError("fpcalc")

    with pytest.raises(FingerprintError, match="fpcalc"):
        fingerprint_file(song, runner=runner)


def test_timeout_is_user_readable(tmp_path: Path) -> None:
    song = tmp_path / "song.flac"
    song.write_bytes(b"")

    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fpcalc", timeout=30)

    with pytest.raises(FingerprintError, match="timed out"):
        fingerprint_file(song, runner=runner)
