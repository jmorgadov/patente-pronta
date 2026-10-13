from pathlib import Path

import pytest

from patente_pronta.settings import load_settings


def test_load_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", "/data")
    monkeypatch.setenv("DB_PATH", "study.db")

    settings = load_settings()

    assert settings.data_dir == Path("/data")
    assert settings.db_path == Path("study.db")


@pytest.mark.parametrize("missing", ["DATA_DIR", "DB_PATH"])
def test_load_settings_requires_variables(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    monkeypatch.setenv("DATA_DIR", "/data")
    monkeypatch.setenv("DB_PATH", "study.db")
    monkeypatch.delenv(missing)

    with pytest.raises(RuntimeError, match=missing):
        load_settings()
