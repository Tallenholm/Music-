import shutil
from pathlib import Path

import pytest

from music_app.identify.fingerprint import fingerprint_file


def test_fpcalc_fingerprints_real_audio(real_mp3: Path) -> None:
    if not shutil.which("fpcalc"):
        pytest.skip("fpcalc is not installed")

    result = fingerprint_file(real_mp3)

    assert result.duration_s > 1.0
    assert len(result.fingerprint) > 20
