import random
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select
from sqlmodel.sql.expression import SelectOfScalar

from patente_pronta.models import (
    Attempt,
    AttemptAnswer,
    Chapter,
    Level,
    Mode,
    Pool,
    Question,
    QuestionFilter,
    Reask,
    Topic,
    UnlimitedRun,
)
from patente_pronta.quiz import (
    EXAM_DURATION,
    Candidate,
    RunStats,
    draw_exam,
    draw_from_pool,
    draw_practice,
    next_reask_step,
    reask_position,
    run_stats,
    shuffle_pool,
)


def start_exam(
    session: Session, levels: Sequence[Level], pool: Pool, rng: random.Random, now: datetime
) -> Attempt:
    rows = session.exec(
        select(Question.id, Question.topic_id).where(*_drawable(levels, pool))
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
    pool: Pool,
    instant_feedback: bool,
    rng: random.Random,
    now: datetime,
) -> Attempt:
    question_ids = draw_practice(_drawable_ids(session, levels, chapter_ids, pool), count, rng)
    return _create_attempt(
        session, Mode.PRACTICE, levels, instant_feedback, question_ids, now, None
    )


def start_unlimited(
    session: Session,
    levels: Sequence[Level],
    chapter_ids: Sequence[int],
    pool: Pool,
    show_level: bool,
    rng: random.Random,
    now: datetime,
) -> Attempt:
    order = shuffle_pool(_drawable_ids(session, levels, chapter_ids, pool), rng)
    attempt = _create_attempt(session, Mode.UNLIMITED, levels, True, order[:1], now, None)
    run = UnlimitedRun(attempt_id=_id(attempt), show_level=show_level, order=order, cursor=1)
    session.add(run)
    session.commit()
    session.refresh(attempt)
    return attempt


def answer_unlimited(
    session: Session,
    attempt: Attempt,
    position: int,
    given: bool,
    rng: random.Random,
    now: datetime,
) -> AttemptAnswer:
    answer = _current_unlimited(attempt, position, now)
    answer.given = given
    return _advance(session, attempt, answer, rng)


def reveal_unlimited(
    session: Session, attempt: Attempt, position: int, rng: random.Random, now: datetime
) -> AttemptAnswer:
    answer = _current_unlimited(attempt, position, now)
    answer.revealed = True
    return _advance(session, attempt, answer, rng)


def finish_unlimited(session: Session, attempt: Attempt, now: datetime) -> bool:
    attempt_id = _id(attempt)
    for reask in _reasks(session, attempt_id):
        session.delete(reask)
    for answer in attempt.answers:
        if not answer.is_done:
            session.delete(answer)
    session.commit()
    session.refresh(attempt)
    if attempt.answers:
        finish(session, attempt, now)
        return True
    session.delete(unlimited_run(session, attempt))
    session.delete(attempt)
    session.commit()
    return False


def unlimited_run(session: Session, attempt: Attempt) -> UnlimitedRun:
    run = session.get(UnlimitedRun, attempt.id)
    if run is None:
        msg = f"Attempt {attempt.id} has no unlimited run"
        raise LookupError(msg)
    return run


def unlimited_stats(attempt: Attempt) -> RunStats:
    return run_stats([answer.is_correct for answer in attempt.answers if answer.is_done])


def is_reask(session: Session, answer: AttemptAnswer) -> bool:
    found = session.exec(
        select(Reask.id).where(
            Reask.attempt_id == answer.attempt_id, Reask.asked_at == answer.position
        )
    ).first()
    return found is not None


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
    answer.question.seen = True
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
    answer.question.seen = True
    return _saved(session, answer)


def finish(session: Session, attempt: Attempt, now: datetime) -> None:
    if attempt.finished_at is not None:
        return
    attempt.finished_at = now
    attempt.correct = sum(answer.is_correct for answer in attempt.answers)
    for answer in attempt.answers:
        answer.level = answer.question.level
    session.add(attempt)
    session.add_all(attempt.answers)
    session.commit()


def is_expired(attempt: Attempt, now: datetime) -> bool:
    return attempt.deadline is not None and now > attempt.deadline


def remaining_seconds(attempt: Attempt, now: datetime) -> int:
    if attempt.deadline is None:
        msg = f"Attempt {attempt.id} has no time limit"
        raise ValueError(msg)
    return max(0, int((attempt.deadline - now).total_seconds()))


def set_level(session: Session, question_id: int, level: Level) -> Question:
    question = _question(session, question_id)
    question.level = level
    return _saved_question(session, question)


def reset_level(session: Session, question_id: int) -> Question:
    question = _question(session, question_id)
    return set_level(session, question_id, question.default_level)


def set_seen(session: Session, question_id: int, seen: bool) -> Question:
    question = _question(session, question_id)
    question.seen = seen
    return _saved_question(session, question)


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


def filtered_questions(session: Session, question_filter: QuestionFilter) -> Sequence[Question]:
    return session.exec(
        select(Question)
        .join(Topic)
        .where(*_filtered(question_filter))
        .order_by(col(Question.id))
        .options(selectinload(Question.topic).selectinload(Topic.chapter))  # type: ignore[arg-type]
    ).all()


def completed_attempts(session: Session) -> list[Attempt]:
    attempts = session.exec(
        select(Attempt)
        .where(col(Attempt.finished_at).is_not(None))
        .order_by(col(Attempt.finished_at))
        .options(selectinload(Attempt.answers))  # type: ignore[arg-type]
    ).all()
    return [attempt for attempt in attempts if attempt.is_complete]


def level_totals(session: Session) -> dict[Level, int]:
    return _counts_by_level(session, [])


def seen_totals(session: Session) -> dict[Level, int]:
    return _counts_by_level(session, [col(Question.seen).is_(True)])


def _drawable_ids(
    session: Session, levels: Sequence[Level], chapter_ids: Sequence[int], pool: Pool
) -> list[int]:
    rows = session.exec(
        select(Question.id)
        .join(Topic)
        .where(*_drawable(levels, pool), col(Topic.chapter_id).in_(chapter_ids))
    ).all()
    return [qid for qid in rows if qid]


def _drawable(levels: Sequence[Level], pool: Pool) -> list[ColumnElement[bool]]:
    return [col(Question.level).in_(levels), *_in_pool(pool)]


def _filtered(question_filter: QuestionFilter) -> list[ColumnElement[bool]]:
    conditions = _in_pool(question_filter.pool)
    if question_filter.number is not None:
        number = question_filter.number
        conditions.append(or_(col(Question.id) == number, col(Question.topic_id) == number))
    if question_filter.chapter_id is not None:
        conditions.append(col(Topic.chapter_id) == question_filter.chapter_id)
    if question_filter.answer is not None:
        conditions.append(col(Question.answer).is_(question_filter.answer))
    if question_filter.levels:
        conditions.append(col(Question.level).in_(question_filter.levels))
    return conditions


def _in_pool(pool: Pool) -> list[ColumnElement[bool]]:
    match pool:
        case Pool.SEEN:
            return [col(Question.seen).is_(True)]
        case Pool.UNSEEN:
            return [col(Question.seen).is_(False)]
        case Pool.WRONG:
            return [col(Question.id).in_(_last_answered_wrong())]
        case Pool.ALL:
            return []


def _last_answered_wrong() -> SelectOfScalar[int]:
    done = or_(col(AttemptAnswer.given).is_not(None), col(AttemptAnswer.revealed))
    latest = (
        select(AttemptAnswer.question_id, func.max(AttemptAnswer.attempt_id).label("attempt_id"))
        .where(done)
        .group_by(col(AttemptAnswer.question_id))
        .subquery()
    )
    return (
        select(AttemptAnswer.question_id)
        .join(
            latest,
            and_(
                col(AttemptAnswer.question_id) == latest.c.question_id,
                col(AttemptAnswer.attempt_id) == latest.c.attempt_id,
            ),
        )
        .join(Question)
        .where(or_(col(AttemptAnswer.revealed), col(AttemptAnswer.given) != col(Question.answer)))
    )


def _counts_by_level(
    session: Session, conditions: Sequence[ColumnElement[bool]]
) -> dict[Level, int]:
    rows = session.exec(
        select(Question.level, func.count()).where(*conditions).group_by(col(Question.level))
    ).all()
    totals = dict.fromkeys(Level, 0)
    for level, count in rows:
        totals[Level(level)] = count
    return totals


def _question(session: Session, question_id: int) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        msg = f"No question with id {question_id}"
        raise LookupError(msg)
    return question


def _saved_question(session: Session, question: Question) -> Question:
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


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


def _current_unlimited(attempt: Attempt, position: int, now: datetime) -> AttemptAnswer:
    answer = _open_answer(attempt, position, now)
    if answer.is_done:
        msg = f"Question {position} of attempt {attempt.id} is already done"
        raise ValueError(msg)
    return answer


def _advance(
    session: Session, attempt: Attempt, answered: AttemptAnswer, rng: random.Random
) -> AttemptAnswer:
    attempt_id = _id(attempt)
    answered.question.seen = True
    run = unlimited_run(session, attempt)
    pending = _reschedule(session, attempt_id, answered, rng)
    upcoming = AttemptAnswer(
        attempt_id=attempt_id,
        position=answered.position + 1,
        question_id=_next_question(run, pending, answered, rng),
        given=None,
        revealed=False,
        level=None,
    )
    session.add_all([answered, answered.question, run, upcoming])
    session.commit()
    session.refresh(upcoming)
    return upcoming


def _reschedule(
    session: Session, attempt_id: int, answered: AttemptAnswer, rng: random.Random
) -> list[Reask]:
    reasks = _reasks(session, attempt_id)
    asked = next((reask for reask in reasks if reask.asked_at == answered.position), None)
    step = next_reask_step(answered.is_correct, asked.step if asked else None)
    pending: list[Reask] = []
    for reask in reasks:
        if reask.asked_at is None and reask.question_id != answered.question_id:
            pending.append(reask)
        else:
            session.delete(reask)
    if step is not None:
        reask = Reask(
            attempt_id=attempt_id,
            question_id=answered.question_id,
            step=step,
            due=reask_position(answered.position, step, rng),
            asked_at=None,
        )
        session.add(reask)
        pending.append(reask)
    return pending


def _next_question(
    run: UnlimitedRun, pending: Sequence[Reask], answered: AttemptAnswer, rng: random.Random
) -> int:
    position = answered.position + 1
    reask = min((r for r in pending if r.due <= position), key=_due, default=None)
    if reask is None:
        avoid = {r.question_id for r in pending} | {answered.question_id}
        draw = draw_from_pool(run.order, run.cursor, avoid, rng)
        if draw is not None:
            run.order, run.cursor = draw.order, draw.cursor
            return draw.question_id
        reask = min(pending, key=_due, default=None)
    if reask is None:
        return answered.question_id
    reask.asked_at = position
    return reask.question_id


def _due(reask: Reask) -> int:
    return reask.due


def _reasks(session: Session, attempt_id: int) -> Sequence[Reask]:
    return session.exec(select(Reask).where(Reask.attempt_id == attempt_id)).all()


def _id(attempt: Attempt) -> int:
    if attempt.id is None:
        msg = "Attempt has no id after flush"
        raise RuntimeError(msg)
    return attempt.id


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
    attempt_id = _id(attempt)
    session.add_all(
        AttemptAnswer(
            attempt_id=attempt_id,
            position=position,
            question_id=qid,
            given=None,
            revealed=False,
            level=None,
        )
        for position, qid in enumerate(question_ids, start=1)
    )
    session.commit()
    session.refresh(attempt)
    return attempt
