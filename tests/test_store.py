import random
from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from patente_pronta import store
from patente_pronta.models import Level

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


def test_reveal_is_only_for_practice(session: Session) -> None:
    attempt = store.start_exam(session, list(Level), random.Random(1), NOW)

    with pytest.raises(ValueError, match="only be revealed in practice"):
        store.reveal_answer(session, attempt, 1, NOW)


def test_remaining_seconds_needs_a_deadline(session: Session) -> None:
    attempt = store.start_practice(session, list(Level), [1], 3, True, random.Random(1), NOW)

    with pytest.raises(ValueError, match="no time limit"):
        store.remaining_seconds(attempt, NOW)


def test_level_totals_cover_every_level(session: Session) -> None:
    assert store.level_totals(session) == {Level.EASY: 70, Level.MEDIUM: 80, Level.HARD: 10}
