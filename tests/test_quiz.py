import random

import pytest

from patente_pronta.errors import NotEnoughQuestionsError
from patente_pronta.quiz import EXAM_SIZE, Candidate, draw_exam, draw_practice, is_passed


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
