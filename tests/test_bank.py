from pathlib import Path

from sqlmodel import Session, func, select

from patente_pronta import bank
from patente_pronta.models import Chapter, Level, Question, Topic


def test_load_creates_the_whole_hierarchy(session: Session) -> None:
    assert session.exec(select(func.count()).select_from(Chapter)).one() == 4
    assert session.exec(select(func.count()).select_from(Topic)).one() == 40
    assert session.exec(select(func.count()).select_from(Question)).one() == 160


def test_load_keeps_source_ids_and_titles(session: Session) -> None:
    chapter = session.get(Chapter, 1)
    assert chapter is not None
    assert chapter.title == "Capitolo 1"
    assert chapter.full_title == "Capitolo 1; titolo completo"
    assert [topic.id for topic in chapter.topics] == list(range(4001, 4011))
    assert {question.id for question in chapter.topics[0].questions} == {40010, 40011, 40012, 40013}


def test_load_maps_answers_and_levels(session: Session) -> None:
    by_text = _questions(session, 4001)

    true_a = by_text["4001 true A"]
    assert true_a.answer is True
    assert true_a.level == Level.EASY
    assert true_a.default_level == Level.EASY
    assert by_text["4001 false A"].answer is False
    assert by_text["4001 false A"].level == Level.MEDIUM
    assert by_text["4001 false B"].level == Level.HARD


def test_figures_shared_by_every_question_belong_to_the_topic(session: Session) -> None:
    topic = session.get(Topic, 4001)
    assert topic is not None

    assert topic.figures == ["figures/1.png"]
    assert all(question.figures == ["figures/1.png"] for question in topic.questions)


def test_figures_of_single_questions_stay_on_the_question(session: Session) -> None:
    topic = session.get(Topic, 4002)
    assert topic is not None
    by_text = _questions(session, 4002)

    assert topic.figures == []
    assert by_text["4002 false A"].figures == ["figures/2.png"]
    assert by_text["4002 true A"].figures == []


def test_questions_are_not_ordered_by_answer(session: Session) -> None:
    answers = [
        [question.answer for question in topic.questions]
        for topic in session.exec(select(Topic)).all()
    ]

    assert any(order != [True, True, False, False] for order in answers)


def test_load_if_empty_does_not_duplicate(session: Session, data_dir: Path) -> None:
    bank.load_if_empty(session, data_dir)

    assert session.exec(select(func.count()).select_from(Question)).one() == 160


def _questions(session: Session, topic_id: int) -> dict[str, Question]:
    topic = session.get(Topic, topic_id)
    assert topic is not None
    return {question.text: question for question in topic.questions}
