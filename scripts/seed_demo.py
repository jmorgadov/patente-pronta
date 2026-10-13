"""Fill a separate demo database with a few weeks of made-up study history.

Run from the repository root: `uv run python scripts/seed_demo.py`. It rewrites
`data/demo.db` and never touches the real `data/patente.db`.
"""

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from patente_pronta import store
from patente_pronta.main import create_app
from patente_pronta.models import Attempt, Chapter, Level, Question
from patente_pronta.settings import Settings

DATA_DIR = Path("data")
DEMO_DB = DATA_DIR / "demo.db"
SEED = 2026
EXAM_CORRECT = [21, 23, 24, 26, 25, 27, 28, 29, 30]
PRACTICE_RATES = [0.55, 0.62, 0.66, 0.7, 0.74, 0.78, 0.83, 0.86, 0.9]
PRACTICE_SIZE = 20
RELABELLED_QUESTIONS = 150
REVEAL_CHANCE = 0.3


def main() -> None:
    DEMO_DB.unlink(missing_ok=True)
    app = create_app(Settings(data_dir=DATA_DIR, db_path=DEMO_DB))
    rng = random.Random(SEED)
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    first_day = today - timedelta(days=25)
    with Session(app.state.engine) as session:
        _relabel_levels(session, rng)
        chapters = [chapter.id for chapter in session.exec(select(Chapter)).all()]
        for index, (exam_correct, practice_rate) in enumerate(
            zip(EXAM_CORRECT, PRACTICE_RATES, strict=True)
        ):
            evening = first_day + timedelta(days=index * 3, hours=17)
            practice = store.start_practice(
                session, list(Level), rng.sample(chapters, 4), PRACTICE_SIZE, rng, evening
            )
            _play(session, practice, round(practice_rate * PRACTICE_SIZE), rng, evening)
            exam_start = evening + timedelta(minutes=40)
            exam = store.start_exam(session, list(Level), rng, exam_start)
            _play(session, exam, exam_correct, rng, exam_start)
    app.state.engine.dispose()
    print(f"Demo database written to {DEMO_DB}")


def _relabel_levels(session: Session, rng: random.Random) -> None:
    question_ids = list(session.exec(select(Question.id)).all())
    for question_id in rng.sample(question_ids, RELABELLED_QUESTIONS):
        store.set_level(session, question_id, rng.choice(list(Level)))


def _play(
    session: Session, attempt: Attempt, correct: int, rng: random.Random, started: datetime
) -> None:
    answers = list(attempt.answers)
    right = set(rng.sample(range(len(answers)), min(correct, len(answers))))
    answered_at = started + timedelta(minutes=12)
    for index, answer in enumerate(answers):
        truth = answer.question.answer
        if index not in right and attempt.deadline is None and rng.random() < REVEAL_CHANCE:
            store.reveal_answer(session, attempt, answer.position, answered_at)
            continue
        given = truth if index in right else not truth
        store.record_answer(session, attempt, answer.position, given, answered_at)
    store.finish(session, attempt, answered_at + timedelta(minutes=2))


if __name__ == "__main__":
    main()
