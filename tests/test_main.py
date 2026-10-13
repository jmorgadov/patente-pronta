from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from patente_pronta.main import create_app_from_env


def test_create_app_from_env(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "env.db"))

    app = create_app_from_env()
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/figures/1.png").content == b"png"
        assert client.get("/static/style.css").status_code == 200
    app.state.engine.dispose()
