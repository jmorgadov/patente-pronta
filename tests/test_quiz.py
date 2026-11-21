import random

import pytest

from patente_pronta.errors import NotEnoughQuestionsError
from patente_pronta.quiz import (
    EXAM_SIZE,
    REASK_GAPS,
    Candidate,
    RunStats,
    draw_exam,
    draw_from_pool,
    draw_practice,
    is_passed,
    next_reask_step,
    reask_position,
    run_stats,
    shuffle_pool,
)


def test_draw_exam_picks_one_question_per_topic() -> None:
    candidates = [
        Candidate(question_id=topic * 10 + n, topic_id=topic)
        for topic in range(40)
        for n in range(4)
    ]

    picked = draw_exam(candidates, random.Random(1))

    assert len(picked) == EXAM_SIZE
    assert len({question_id // 10 for question_id in picked}) == EXAM_SIZE


def test_draw_exam_fails_without_enough_topics() -> None:
    candidates = [Candidate(question_id=n, topic_id=n % 29) for n in range(200)]

    with pytest.raises(NotEnoughQuestionsError):
        draw_exam(candidates, random.Random(1))


@pytest.mark.parametrize(("available", "count", "expected"), [(50, 30, 30), (12, 30, 12)])
def test_draw_practice_caps_at_available(available: int, count: int, expected: int) -> None:
    picked = draw_practice(list(range(available)), count, random.Random(1))

    assert len(picked) == expected
    assert len(set(picked)) == expected


def test_draw_practice_fails_without_questions() -> None:
    with pytest.raises(NotEnoughQuestionsError):
        draw_practice([], 10, random.Random(1))


def test_draw_practice_rejects_non_positive_count() -> None:
    with pytest.raises(ValueError, match="almeno 1"):
        draw_practice([1, 2, 3], 0, random.Random(1))


@pytest.mark.parametrize(("correct", "passed"), [(26, False), (27, True), (30, True)])
def test_is_passed(correct: int, passed: bool) -> None:
    assert is_passed(correct) is passed


@pytest.mark.parametrize(
    ("correct", "answered_step", "expected"),
    [
        (False, None, 0),
        (False, 1, 0),
        (False, 2, 0),
        (True, None, None),
        (True, 0, 1),
        (True, 1, 2),
        (True, 2, None),
    ],
)
def test_next_reask_step(correct: bool, answered_step: int | None, expected: int | None) -> None:
    assert next_reask_step(correct, answered_step) == expected


@pytest.mark.parametrize("step", range(len(REASK_GAPS)))
def test_reask_position_stays_within_the_step_gap(step: int) -> None:
    rng = random.Random(5)
    low, high = REASK_GAPS[step]

    gaps = {reask_position(100, step, rng) - 100 for _ in range(200)}

    assert gaps == set(range(low, high + 1))


def test_draw_from_pool_walks_the_order_then_reshuffles() -> None:
    rng = random.Random(2)
    order, cursor, drawn = [1, 2, 3, 4], 0, []
    for _ in range(8):
        draw = draw_from_pool(order, cursor, set(), rng)
        assert draw is not None
        drawn.append(draw.question_id)
        order, cursor = draw.order, draw.cursor

    assert drawn[:4] == [1, 2, 3, 4]
    assert sorted(drawn[4:]) == [1, 2, 3, 4]


def test_draw_from_pool_skips_avoided_questions() -> None:
    draw = draw_from_pool([1, 2, 3], 0, {1, 2}, random.Random(1))

    assert draw is not None
    assert (draw.question_id, draw.cursor) == (3, 3)


def test_draw_from_pool_looks_past_the_reshuffle() -> None:
    draw = draw_from_pool([1, 2, 3, 4], 1, {2, 3, 4}, random.Random(1))

    assert draw is not None
    assert draw.question_id == 1


def test_draw_from_pool_gives_up_when_everything_is_avoided() -> None:
    assert draw_from_pool([1, 2], 1, {1, 2}, random.Random(1)) is None


def test_shuffle_pool_keeps_every_question() -> None:
    assert sorted(shuffle_pool([3, 1, 2], random.Random(1))) == [1, 2, 3]


def test_shuffle_pool_fails_without_questions() -> None:
    with pytest.raises(NotEnoughQuestionsError):
        shuffle_pool([], random.Random(1))


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([], RunStats(0, 0, 0, 0, ())),
        ([True, True, False, True], RunStats(4, 3, 2, 1, (True, True, False, True))),
        ([False] * 5 + [True] * 30, RunStats(35, 30, 30, 30, (True,) * 30)),
        ([True] * 10 + [False] * 30, RunStats(40, 10, 10, 0, (False,) * 30)),
    ],
)
def test_run_stats(results: list[bool], expected: RunStats) -> None:
    assert run_stats(results) == expected
