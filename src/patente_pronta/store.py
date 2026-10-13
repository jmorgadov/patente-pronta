import random
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from patente_pronta.models import Attempt, AttemptAnswer, Chapter, Level, Mode, Question, Topic
from patente_pronta.quiz import EXAM_DURATION, Candidate, draw_exam, draw_practice


def start_exam(
    session: Session, levels: Sequence[Level], rng: random.Random, now: datetime
) -> Attempt:
    rows = session.exec(
        select(Question.id, Question.topic_id).where(col(Question.level).in_(levels))
    ).all()
    candidates = [Candidate(question_id=qid, topic_id=tid) for qid, tid in rows if qid]
    question_ids = draw_exam(candidates, rng)
    return _create_attempt(
        session, Mode.EXAM, levels, False, question_ids, now, now + EXAM_DURATION
    )


def start_practice(
    session: Session,
    levels: Sequence[Level],
    chapter_ids: Sequence[int],
    count: int,
    instant_feedback: bool,
    rng: random.Random,
    now: datetime,
) -> Attempt:
    rows = session.exec(
        select(Question.id)
        .join(Topic)
        .where(col(Question.level).in_(levels), col(Topic.chapter_id).in_(chapter_ids))
    ).all()
    question_ids = draw_practice([qid for qid in rows if qid], count, rng)
    return _create_attempt(
        session, Mode.PRACTICE, levels, instant_feedback, question_ids, now, None
    )


def get_attempt(session: Session, attempt_id: int, mode: Mode) -> Attempt:
    attempt = session.exec(
        select(Attempt)
        .where(Attempt.id == attempt_id, Attempt.mode == mode)
        .options(
            selectinload(Attempt.answers)  # type: ignore[arg-type]
            .selectinload(AttemptAnswer.question)  # type: ignore[arg-type]
            .selectinload(Question.topic)  # type: ignore[arg-type]
            .selectinload(Topic.chapter)  # type: ignore[arg-type]
        )
    ).first()
    if attempt is None:
        msg = f"No {mode} attempt with id {attempt_id}"
        raise LookupError(msg)
    return attempt


def record_answer(
    session: Session, attempt: Attempt, position: int, given: bool, now: datetime
) -> AttemptAnswer:
    answer = _open_answer(attempt, position, now)
    if answer.revealed:
        msg = f"Question {position} of attempt {attempt.id} was revealed; it cannot be answered"
        raise ValueError(msg)
    answer.given = given
    return _saved(session, answer)


def reveal_answer(
    session: Session, attempt: Attempt, position: int, now: datetime
) -> AttemptAnswer:
    if attempt.mode != Mode.PRACTICE:
        msg = f"Answers can only be revealed in practice, not in {attempt.mode}"
        raise ValueError(msg)
    answer = _open_answer(attempt, position, now)
    if answer.given is not None:
        msg = f"Question {position} of attempt {attempt.id} is already answered"
        raise ValueError(msg)
    answer.revealed = True
    return _saved(session, answer)


def finish(session: Session, attempt: Attempt, now: datetime) -> None:
    if attempt.finished_at is not None:
        return
    attempt.finished_at = now
    attempt.correct = sum(answer.is_correct for answer in attempt.answers)
    session.add(attempt)
    session.commit()


def is_expired(attempt: Attempt, now: datetime) -> bool:
    return attempt.deadline is not None and now > attempt.deadline


def remaining_seconds(attempt: Attempt, now: datetime) -> int:
    if attempt.deadline is None:
        msg = f"Attempt {attempt.id} has no time limit"
        raise ValueError(msg)
    return max(0, int((attempt.deadline - now).total_seconds()))


def set_level(session: Session, question_id: int, level: Level) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        msg = f"No question with id {question_id}"
        raise LookupError(msg)
    question.level = level
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def reset_level(session: Session, question_id: int) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        msg = f"No question with id {question_id}"
        raise LookupError(msg)
    return set_level(session, question_id, question.default_level)


def chapters(session: Session) -> Sequence[Chapter]:
    return session.exec(select(Chapter).order_by(col(Chapter.id))).all()


def chapter(session: Session, chapter_id: int) -> Chapter:
    found = session.exec(
        select(Chapter)
        .where(Chapter.id == chapter_id)
        .options(selectinload(Chapter.topics).selectinload(Topic.questions))  # type: ignore[arg-type]
    ).first()
    if found is None:
        msg = f"No chapter with id {chapter_id}"
        raise LookupError(msg)
    return found


def level_counts_by_chapter(session: Session) -> dict[int, dict[Level, int]]:
    rows = session.exec(
        select(Topic.chapter_id, Question.level, func.count())
        .join(Topic)
        .group_by(col(Topic.chapter_id), col(Question.level))
    ).all()
    counts: dict[int, dict[Level, int]] = {}
    for chapter_id, level, count in rows:
        counts.setdefault(chapter_id, dict.fromkeys(Level, 0))[Level(level)] = count
    return counts


def completed_attempts(session: Session) -> list[Attempt]:
    attempts = session.exec(
        select(Attempt)
        .where(col(Attempt.finished_at).is_not(None))
        .order_by(col(Attempt.finished_at))
        .options(selectinload(Attempt.answers))  # type: ignore[arg-type]
    ).all()
    return [attempt for attempt in attempts if attempt.is_complete]


def level_totals(session: Session) -> dict[Level, int]:
    rows = session.exec(select(Question.level, func.count()).group_by(col(Question.level))).all()
    totals = dict.fromkeys(Level, 0)
    for level, count in rows:
        totals[Level(level)] = count
    return totals


def _open_answer(attempt: Attempt, position: int, now: datetime) -> AttemptAnswer:
    if attempt.finished_at is not None or is_expired(attempt, now):
        msg = f"Attempt {attempt.id} is already over"
        raise ValueError(msg)
    answer = next((a for a in attempt.answers if a.position == position), None)
    if answer is None:
        msg = f"Attempt {attempt.id} has no question at position {position}"
        raise LookupError(msg)
    return answer


def _saved(session: Session, answer: AttemptAnswer) -> AttemptAnswer:
    session.add(answer)
    session.commit()
    session.refresh(answer)
    return answer


def _create_attempt(
    session: Session,
    mode: Mode,
    levels: Sequence[Level],
    instant_feedback: bool,
    question_ids: Sequence[int],
    now: datetime,
    deadline: datetime | None,
) -> Attempt:
    attempt = Attempt(
        mode=mode,
        levels=",".join(levels),
        instant_feedback=instant_feedback,
        started_at=now,
        deadline=deadline,
        finished_at=None,
        correct=None,
    )
    session.add(attempt)
    session.flush()
    if attempt.id is None:
        msg = "Attempt has no id after flush"
        raise RuntimeError(msg)
    session.add_all(
        AttemptAnswer(
            attempt_id=attempt.id, position=position, question_id=qid, given=None, revealed=False
        )
        for position, qid in enumerate(question_ids, start=1)
    )
    session.commit()
    session.refresh(attempt)
    return attempt
