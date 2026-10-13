import json
import random
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from patente_pronta.main import create_app
from patente_pronta.settings import Settings
from patente_pronta.web import get_now, get_rng

TOPICS_PER_CHAPTER = 10
HARD_TOPICS = 10
START = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "data"
    (directory / "figures").mkdir(parents=True)
    (directory / "figures" / "1.png").write_bytes(b"png")
    (directory / "figures" / "2.png").write_bytes(b"png")
    (directory / "quiz.json").write_text(json.dumps(build_bank(), indent=2))
    return directory


@pytest.fixture
def clock() -> Clock:
    return Clock(START)


@pytest.fixture
def app(data_dir: Path, tmp_path: Path, clock: Clock) -> Iterator[FastAPI]:
    application = create_app(Settings(data_dir=data_dir, db_path=tmp_path / "test.db"))
    application.dependency_overrides[get_rng] = lambda: random.Random(7)
    application.dependency_overrides[get_now] = lambda: clock.now
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(app: FastAPI) -> Iterator[Session]:
    with Session(app.state.engine) as db_session:
        yield db_session


def build_bank() -> dict[str, Any]:
    """Four chapters x 10 quesiti, each with 2 true and 2 false questions.

    Every quesito has Easy and Medium questions; only the first 10 have a Hard one.
    Even quesiti share figure 1 on every question; in odd ones only "false A" has figure 2.
    """
    chapters = []
    topic_number = 0
    for chapter_index in range(4):
        quesiti = []
        for _ in range(TOPICS_PER_CHAPTER):
            quesito_id = 4001 + topic_number
            is_hard = topic_number < HARD_TOPICS
            shared = ["1"] if topic_number % 2 == 0 else []
            specs = [
                ("true A", True, "easy", shared),
                ("true B", True, "medium", shared),
                ("false A", False, "medium", shared or ["2"]),
                ("false B", False, "hard" if is_hard else "easy", shared),
            ]
            quesiti.append(
                {
                    "id": quesito_id,
                    "questions": [
                        {
                            "id": quesito_id * 10 + index,
                            "q": f"{quesito_id} {label}",
                            "answer": answer,
                            "figures": figures,
                            "level": level,
                        }
                        for index, (label, answer, level, figures) in enumerate(specs)
                    ],
                }
            )
            topic_number += 1
        chapters.append(
            {
                "id": chapter_index + 1,
                "title": f"Capitolo {chapter_index + 1}",
                "full_title": f"Capitolo {chapter_index + 1}; titolo completo",
                "quesiti": quesiti,
            }
        )
    return {
        "source": "test",
        "figures": {"1": "figures/1.png", "2": "figures/2.png"},
        "chapters": chapters,
    }
