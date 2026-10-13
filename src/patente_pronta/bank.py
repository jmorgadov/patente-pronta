import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from patente_pronta.models import Chapter, Level, Question, Topic

logger = logging.getLogger(__name__)


def load_if_empty(session: Session, data_dir: Path) -> None:
    if session.exec(select(Question.id).limit(1)).first() is not None:
        return
    load(session, data_dir)


def load(session: Session, data_dir: Path) -> None:
    quiz = json.loads((data_dir / "quiz.json").read_text())
    figures: dict[str, str] = quiz["figures"]
    for chapter in quiz["chapters"]:
        session.add(
            Chapter(id=chapter["id"], title=chapter["title"], full_title=chapter["full_title"])
        )
        for quesito in chapter["quesiti"]:
            questions = _questions(quesito, figures)
            session.add(
                Topic(id=quesito["id"], chapter_id=chapter["id"], figures=_shared(questions))
            )
            session.add_all(questions)
    session.commit()
    logger.info("Loaded question bank from %s", data_dir)


def _questions(quesito: dict[str, Any], figures: dict[str, str]) -> list[Question]:
    items = sorted(quesito["questions"], key=_mixing_key)
    return [
        Question(
            id=item["id"],
            topic_id=quesito["id"],
            position=position,
            text=item["q"],
            answer=item["answer"],
            figures=[figures[key] for key in item["figures"]],
            level=Level(item["level"]),
            default_level=Level(item["level"]),
        )
        for position, item in enumerate(items, start=1)
    ]


def _shared(questions: list[Question]) -> list[str]:
    first = questions[0].figures
    return first if all(question.figures == first for question in questions) else []


def _mixing_key(item: dict[str, Any]) -> str:
    # The source lists true statements before false ones; a stable hash order hides that.
    return hashlib.sha256(item["q"].encode()).hexdigest()
