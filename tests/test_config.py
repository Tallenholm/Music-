from pathlib import Path

from music_app.config import AppConfig


def test_config_round_trip_uses_requested_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MUSIC_APP_CONFIG_DIR", str(tmp_path))
    config = AppConfig(
        acoustid_client_key="abc123",
        enable_acoustid=True,
        enable_itunes=False,
        enable_ai=True,
        preselect_confidence=0.96,
        rename_template="{artist} - {title}",
    )

    config.save()
    loaded = AppConfig.load()

    assert loaded == config
    assert (tmp_path / "config.json").exists()
