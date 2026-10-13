import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from patente_pronta.errors import NotEnoughQuestionsError

EXAM_SIZE = 30
EXAM_PASS_MARK = 27
EXAM_DURATION = timedelta(minutes=20)


@dataclass(frozen=True, slots=True)
class Candidate:
    question_id: int
    topic_id: int


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
    if not question_ids:
        msg = "Nessuna domanda corrisponde ai filtri scelti"
        raise NotEnoughQuestionsError(msg)
    return rng.sample(list(question_ids), min(count, len(question_ids)))


def is_passed(correct: int) -> bool:
    return correct >= EXAM_PASS_MARK
