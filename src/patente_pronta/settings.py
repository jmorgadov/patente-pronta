import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    db_path: Path


def load_settings() -> Settings:
    return Settings(data_dir=Path(_require_env("DATA_DIR")), db_path=Path(_require_env("DB_PATH")))


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        msg = f"Environment variable {name} is not set; copy .env.example to .env"
        raise RuntimeError(msg)
    return value
