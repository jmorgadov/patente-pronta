import itertools
import random
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlmodel import Session, col, select

from patente_pronta import store
from patente_pronta.errors import NotEnoughQuestionsError
from patente_pronta.models import Attempt, Level, Pool, Question, Topic, UnlimitedRun
from patente_pronta.quiz import REASK_GAPS

Judge = Callable[[int, list[int]], bool]

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


def test_reveal_is_only_for_practice(session: Session) -> None:
    attempt = store.start_exam(session, list(Level), Pool.ALL, random.Random(1), NOW)

    with pytest.raises(ValueError, match="only be revealed in practice"):
        store.reveal_answer(session, attempt, 1, NOW)


def test_remaining_seconds_needs_a_deadline(session: Session) -> None:
    attempt = store.start_practice(
        session, list(Level), [1], 3, Pool.ALL, True, random.Random(1), NOW
    )

    with pytest.raises(ValueError, match="no time limit"):
        store.remaining_seconds(attempt, NOW)


def test_level_totals_cover_every_level(session: Session) -> None:
    assert store.level_totals(session) == {Level.EASY: 70, Level.MEDIUM: 80, Level.HARD: 10}


def test_unlimited_starts_with_one_open_question(session: Session) -> None:
    attempt = _start_unlimited(session, [1], Pool.ALL)

    run = store.unlimited_run(session, attempt)
    assert [answer.is_done for answer in attempt.answers] == [False]
    assert sorted(run.order) == sorted(_question_ids(session, 1, list(Level)))
    assert run.order[0] == attempt.answers[0].question_id


def test_unlimited_without_matching_questions_fails(session: Session) -> None:
    with pytest.raises(NotEnoughQuestionsError):
        store.start_unlimited(session, [Level.HARD], [2], Pool.ALL, True, random.Random(1), NOW)


def test_unlimited_correct_answers_cover_the_pool_before_repeating(session: Session) -> None:
    attempt = _start_unlimited(session, [1], Pool.ALL)

    asked = _play(session, attempt, 41, lambda _, __: True)

    assert len(set(asked[:40])) == 40
    assert asked[40] != asked[39]


def test_unlimited_wrong_answer_comes_back_with_growing_gaps(session: Session) -> None:
    attempt = _start_unlimited(session, [1, 2], Pool.ALL)
    target = attempt.answers[0].question_id

    asked = _play(session, attempt, 60, lambda _, history: len(history) > 1)

    assert _gaps(asked, target) == [REASK_GAPS[0], REASK_GAPS[1], REASK_GAPS[2]]


def test_unlimited_wrong_reask_restarts_the_series(session: Session) -> None:
    attempt = _start_unlimited(session, [1, 2], Pool.ALL)
    target = attempt.answers[0].question_id

    asked = _play(
        session, attempt, 60, lambda qid, history: qid != target or history.count(target) > 2
    )

    assert _gaps(asked, target) == [REASK_GAPS[0], REASK_GAPS[0], REASK_GAPS[1], REASK_GAPS[2]]


def test_unlimited_reveal_counts_as_wrong(session: Session) -> None:
    attempt = _start_unlimited(session, [1], Pool.ALL)
    first = attempt.answers[0]

    upcoming = store.reveal_unlimited(session, attempt, 1, random.Random(1), NOW)

    assert upcoming.position == 2
    assert store.unlimited_stats(attempt).correct == 0
    assert first.question.seen is True
    assert store.is_reask(session, upcoming) is False


def test_unlimited_question_cannot_be_answered_twice(session: Session) -> None:
    attempt = _start_unlimited(session, [1], Pool.ALL)
    store.answer_unlimited(session, attempt, 1, True, random.Random(1), NOW)

    with pytest.raises(ValueError, match="already done"):
        store.answer_unlimited(session, attempt, 1, False, random.Random(1), NOW)


@pytest.mark.parametrize("correct", [True, False])
def test_unlimited_with_one_question_keeps_asking_it(session: Session, correct: bool) -> None:
    only, *others = _question_ids(session, 1, [Level.HARD])
    for question_id in others:
        store.set_seen(session, question_id, True)
    attempt = store.start_unlimited(
        session, [Level.HARD], [1], Pool.UNSEEN, True, random.Random(1), NOW
    )

    asked = _play(session, attempt, 4, lambda _, __: correct)

    assert asked == [only] * 4


def test_unlimited_finish_drops_the_open_question(session: Session) -> None:
    attempt = _start_unlimited(session, [1], Pool.ALL)
    _play(session, attempt, 3, lambda _, __: True)

    kept = store.finish_unlimited(session, attempt, NOW)

    assert kept is True
    assert [answer.position for answer in attempt.answers] == [1, 2, 3]
    assert attempt.correct == 3
    assert attempt.is_complete


def test_unlimited_finish_without_answers_discards_the_run(session: Session) -> None:
    attempt = _start_unlimited(session, [1], Pool.ALL)
    attempt_id = attempt.id

    kept = store.finish_unlimited(session, attempt, NOW)

    assert kept is False
    assert session.get(Attempt, attempt_id) is None
    assert session.get(UnlimitedRun, attempt_id) is None


def _start_unlimited(session: Session, chapters: list[int], pool: Pool) -> Attempt:
    return store.start_unlimited(session, list(Level), chapters, pool, True, random.Random(1), NOW)


def _play(session: Session, attempt: Attempt, count: int, judge: Judge) -> list[int]:
    rng = random.Random(4)
    current = attempt.answers[-1]
    asked: list[int] = []
    for _ in range(count):
        asked.append(current.question_id)
        expected = current.question.answer
        given = expected if judge(current.question_id, asked) else not expected
        current = store.answer_unlimited(session, attempt, current.position, given, rng, NOW)
    return asked


def _gaps(asked: list[int], question_id: int) -> list[tuple[int, int]]:
    positions = [position for position, qid in enumerate(asked) if qid == question_id]
    gaps = [later - earlier for earlier, later in itertools.pairwise(positions)]
    return [next(g for g in REASK_GAPS if g[0] <= gap <= g[1]) for gap in gaps]


def _question_ids(session: Session, chapter_id: int, levels: list[Level]) -> list[int]:
    rows = session.exec(
        select(Question.id)
        .join(Topic)
        .where(Topic.chapter_id == chapter_id, col(Question.level).in_(levels))
        .order_by(col(Question.id))
    ).all()
    return [qid for qid in rows if qid]
