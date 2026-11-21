import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from patente_pronta.errors import NotEnoughQuestionsError

EXAM_SIZE = 30
EXAM_PASS_MARK = 27
EXAM_DURATION = timedelta(minutes=20)
REASK_GAPS = ((3, 7), (8, 12), (16, 24))
RECENT_WINDOW = 30


@dataclass(frozen=True, slots=True)
class Candidate:
    question_id: int
    topic_id: int


@dataclass(frozen=True, slots=True)
class PoolDraw:
    question_id: int
    order: list[int]
    cursor: int


@dataclass(frozen=True, slots=True)
class RunStats:
    answered: int
    correct: int
    best_streak: int
    current_streak: int
    recent: tuple[bool, ...]


def draw_exam(candidates: Sequence[Candidate], rng: random.Random) -> list[int]:
    seen_topics: set[int] = set()
    picked: list[int] = []
    for candidate in rng.sample(list(candidates), len(candidates)):
        if candidate.topic_id in seen_topics:
            continue
        seen_topics.add(candidate.topic_id)
        picked.append(candidate.question_id)
        if len(picked) == EXAM_SIZE:
            return picked
    msg = f"Servono domande da almeno {EXAM_SIZE} argomenti diversi, trovati {len(picked)}"
    raise NotEnoughQuestionsError(msg)


def draw_practice(question_ids: Sequence[int], count: int, rng: random.Random) -> list[int]:
    if count < 1:
        msg = f"Il numero di domande deve essere almeno 1, ricevuto {count}"
        raise ValueError(msg)
    return rng.sample(_available(question_ids), min(count, len(question_ids)))


def shuffle_pool(question_ids: Sequence[int], rng: random.Random) -> list[int]:
    return rng.sample(_available(question_ids), len(question_ids))


def is_passed(correct: int) -> bool:
    return correct >= EXAM_PASS_MARK


def next_reask_step(correct: bool, answered_step: int | None) -> int | None:
    if not correct:
        return 0
    if answered_step is None or answered_step + 1 == len(REASK_GAPS):
        return None
    return answered_step + 1


def reask_position(position: int, step: int, rng: random.Random) -> int:
    low, high = REASK_GAPS[step]
    return position + rng.randint(low, high)


def draw_from_pool(
    order: Sequence[int], cursor: int, avoid: set[int], rng: random.Random
) -> PoolDraw | None:
    current, index = list(order), cursor
    for _ in range(2 * len(current)):
        if index >= len(current):
            current, index = rng.sample(current, len(current)), 0
        candidate = current[index]
        index += 1
        if candidate not in avoid:
            return PoolDraw(question_id=candidate, order=current, cursor=index)
    return None


def run_stats(results: Sequence[bool]) -> RunStats:
    best = streak = 0
    for correct in results:
        streak = streak + 1 if correct else 0
        best = max(best, streak)
    return RunStats(
        answered=len(results),
        correct=sum(results),
        best_streak=best,
        current_streak=streak,
        recent=tuple(results[-RECENT_WINDOW:]),
    )


def _available(question_ids: Sequence[int]) -> list[int]:
    if not question_ids:
        msg = "Nessuna domanda corrisponde ai filtri scelti"
        raise NotEnoughQuestionsError(msg)
    return list(question_ids)
