import json
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from conftest import Clock
from patente_pronta import store
from patente_pronta.models import Attempt, Level, Mode, Question
from patente_pronta.quiz import EXAM_SIZE

ALL_LEVELS = [level.value for level in Level]
QUESTION_ID = 40010


def test_home_links_to_every_section(client: TestClient) -> None:
    page = client.get("/").text

    for path in ("/esame", "/esercitazione", "/domande", "/storico"):
        assert f'href="{path}"' in page


def test_exam_draws_one_question_per_topic(client: TestClient, app: FastAPI) -> None:
    attempt = _attempt(app, _start_exam(client, ALL_LEVELS), Mode.EXAM)

    assert len(attempt.answers) == EXAM_SIZE
    assert len({answer.question.topic_id for answer in attempt.answers}) == EXAM_SIZE
    assert attempt.deadline == attempt.started_at + timedelta(minutes=20)


def test_exam_respects_level_filter(client: TestClient, app: FastAPI) -> None:
    attempt = _attempt(app, _start_exam(client, ["medium"]), Mode.EXAM)

    assert {answer.question.level for answer in attempt.answers} == {Level.MEDIUM}


@pytest.mark.parametrize(
    ("levels", "message"), [([], "Seleziona almeno un livello"), (["hard"], "argomenti diversi")]
)
def test_exam_setup_reports_errors(client: TestClient, levels: list[str], message: str) -> None:
    response = client.post("/esame", data={"level": levels}, follow_redirects=False)

    assert response.status_code == 400
    assert message in response.text


def test_exam_page_hides_answers(client: TestClient) -> None:
    attempt_id = _start_exam(client, ALL_LEVELS)

    page = client.get(f"/esame/{attempt_id}").text

    assert page.count('class="question-card') == EXAM_SIZE
    assert "data-answer=" not in page
    assert 'data-remaining="1200"' in page


@pytest.mark.parametrize(("correct", "verdict"), [(27, "Promosso!"), (26, "Bocciato")])
def test_exam_result(client: TestClient, app: FastAPI, correct: int, verdict: str) -> None:
    attempt_id = _start_exam(client, ALL_LEVELS)
    attempt = _attempt(app, attempt_id, Mode.EXAM)
    for answer in attempt.answers:
        given = answer.question.answer if answer.position <= correct else not answer.question.answer
        _answer(client, f"/esame/{attempt_id}/risposte", answer.position, given)

    response = client.post(f"/esame/{attempt_id}")

    assert response.url.path == f"/esame/{attempt_id}/risultato"
    assert verdict in response.text
    assert f"{correct}/{EXAM_SIZE} corrette" in response.text
    assert _attempt(app, attempt_id, Mode.EXAM).correct == correct


def test_unanswered_exam_questions_count_as_wrong(client: TestClient) -> None:
    attempt_id = _start_exam(client, ALL_LEVELS)

    response = client.post(f"/esame/{attempt_id}")

    assert "Bocciato" in response.text
    assert f"{EXAM_SIZE} senza risposta" in response.text


def test_expired_exam_is_submitted(client: TestClient, clock: Clock) -> None:
    attempt_id = _start_exam(client, ALL_LEVELS)
    _answer(client, f"/esame/{attempt_id}/risposte", 1, True)
    clock.advance(timedelta(minutes=21))

    late = client.post(f"/esame/{attempt_id}/risposte", json={"position": 2, "given": True})
    page = client.get(f"/esame/{attempt_id}")

    assert late.status_code == 409
    assert page.url.path == f"/esame/{attempt_id}/risultato"


def test_unfinished_exam_result_redirects_to_exam(client: TestClient) -> None:
    attempt_id = _start_exam(client, ALL_LEVELS)

    response = client.get(f"/esame/{attempt_id}/risultato", follow_redirects=False)

    assert response.headers["location"] == f"/esame/{attempt_id}"


def test_finished_exam_page_redirects_to_result(client: TestClient) -> None:
    attempt_id = _start_exam(client, ALL_LEVELS)
    client.post(f"/esame/{attempt_id}")

    response = client.get(f"/esame/{attempt_id}", follow_redirects=False)

    assert response.headers["location"] == f"/esame/{attempt_id}/risultato"


def test_practice_respects_filters(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_practice(client, ["easy"], [1], 100)
    attempt = _attempt(app, attempt_id, Mode.PRACTICE)

    assert len(attempt.answers) == 10
    assert {a.question.level for a in attempt.answers} == {Level.EASY}
    assert {a.question.topic.chapter_id for a in attempt.answers} == {1}


def test_practice_page_shows_answers_and_levels(client: TestClient) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1, 2, 3, 4], 5)

    page = client.get(f"/esercitazione/{attempt_id}").text

    assert page.count('class="question-card') == 5
    assert page.count("data-answer=") == 5
    assert page.count('class="level-control"') == 5


def test_practice_setup_shows_answers_right_away_by_default(client: TestClient) -> None:
    page = client.get("/esercitazione").text

    assert 'name="instant_feedback" value="true" checked' in page


def test_practice_setup_collapses_chapters_when_all_are_chosen(client: TestClient) -> None:
    every = client.get("/esercitazione").text
    some = client.post("/esercitazione", data={"chapter": ["1", "2"], "count": "10"}).text

    assert '<details class="chapter-picker" >' in every
    assert "4/4" in every
    assert '<details class="chapter-picker" open>' in some
    assert "2/4" in some


def test_practice_setup_remembers_the_last_started_settings(client: TestClient) -> None:
    _start_practice_with(client, _practice_form(["easy"], [1], 7) | {"unseen_only": "true"})

    page = client.get("/esercitazione").text

    assert 'name="level" value="easy" checked' in page
    assert 'name="level" value="hard" >' in page
    assert 'value="7"' in page
    assert '<details class="chapter-picker" open>' in page
    assert "1/4" in page
    assert 'name="unseen_only" value="true" checked' in page
    assert 'name="instant_feedback" value="true" >' in page


def test_practice_setup_ignores_settings_that_failed_to_start(client: TestClient) -> None:
    client.post("/esercitazione", data={"chapter": ["1"], "count": "7"})

    page = client.get("/esercitazione").text

    assert 'value="30"' in page
    assert "4/4" in page


def test_practice_setup_ignores_a_broken_cookie(client: TestClient) -> None:
    client.cookies.set("practice_settings", "not json")

    page = client.get("/esercitazione").text

    assert 'value="30"' in page
    assert 'name="instant_feedback" value="true" checked' in page


def test_exam_setup_remembers_the_last_started_settings(client: TestClient) -> None:
    response = client.post(
        "/esame", data={"level": ["medium"], "unseen_only": "true"}, follow_redirects=False
    )
    assert response.status_code == 303

    page = client.get("/esame").text

    assert 'name="level" value="medium" checked' in page
    assert 'name="level" value="easy" >' in page
    assert 'name="unseen_only" value="true" checked' in page


def test_blind_practice_page_hides_answers(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_blind_practice(client, [1, 2], 5)

    page = client.get(f"/esercitazione/{attempt_id}").text

    assert _attempt(app, attempt_id, Mode.PRACTICE).instant_feedback is False
    assert page.count('class="question-card') == 5
    assert "data-answer=" not in page
    assert "Mostra la risposta" not in page
    assert page.count('class="strip-cell"') == 5
    assert "Consegna" in page


def test_blind_practice_answers_can_change(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_blind_practice(client, [1], 2)
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 1, True)
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 1, False)

    assert _attempt(app, attempt_id, Mode.PRACTICE).answers[0].given is False


@pytest.mark.parametrize(
    ("levels", "chapters", "message"),
    [
        ([], ["1"], "Seleziona almeno un livello"),
        (ALL_LEVELS, [], "Seleziona almeno un capitolo"),
        (["hard"], ["4"], "Nessuna domanda"),
    ],
)
def test_practice_setup_reports_errors(
    client: TestClient, levels: list[str], chapters: list[str], message: str
) -> None:
    response = client.post(
        "/esercitazione",
        data={"level": levels, "chapter": chapters, "count": "10"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert message in response.text


def test_practice_summary(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)
    first, second, _ = _attempt(app, attempt_id, Mode.PRACTICE).answers
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 1, first.question.answer)
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 2, not second.question.answer)

    response = client.post(f"/esercitazione/{attempt_id}/fine")

    assert response.url.path == f"/esercitazione/{attempt_id}/riepilogo"
    assert "1/3 corrette &middot; 1 sbagliate &middot; 1 senza risposta" in response.text


def test_practice_routes_redirect_by_state(client: TestClient) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)

    early = client.get(f"/esercitazione/{attempt_id}/riepilogo", follow_redirects=False)
    client.post(f"/esercitazione/{attempt_id}/fine")
    late = client.get(f"/esercitazione/{attempt_id}", follow_redirects=False)

    assert early.headers["location"] == f"/esercitazione/{attempt_id}"
    assert late.headers["location"] == f"/esercitazione/{attempt_id}/riepilogo"


def test_answer_for_unknown_position_is_404(client: TestClient) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)

    response = client.post(
        f"/esercitazione/{attempt_id}/risposte", json={"position": 99, "given": True}
    )

    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/esame/999", "/esercitazione/999", "/domande/999"])
def test_unknown_ids_are_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_attempt_is_only_reachable_through_its_mode(client: TestClient) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)

    assert client.get(f"/esame/{attempt_id}").status_code == 404


def test_set_and_reset_level(client: TestClient, app: FastAPI) -> None:
    changed = client.post(f"/api/questions/{QUESTION_ID}/level", json={"level": "hard"})
    question = _question(app, QUESTION_ID)

    assert changed.json() == {"level": "hard", "default_level": question.default_level}
    assert question.level == Level.HARD

    reset = client.post(f"/api/questions/{QUESTION_ID}/level/reset")

    assert reset.json()["level"] == question.default_level
    assert _question(app, QUESTION_ID).level == question.default_level


@pytest.mark.parametrize("path", ["/api/questions/999/level", "/api/questions/999/level/reset"])
def test_level_of_unknown_question_is_404(client: TestClient, path: str) -> None:
    assert client.post(path, json={"level": "hard"}).status_code == 404


def test_changed_level_feeds_the_filters(client: TestClient, app: FastAPI) -> None:
    easy_ids = [
        a.question_id
        for a in _attempt(app, _start_practice(client, ["easy"], [4], 100), Mode.PRACTICE).answers
    ]
    for question_id in easy_ids:
        client.post(f"/api/questions/{question_id}/level", json={"level": "hard"})

    attempt = _attempt(app, _start_practice(client, ["hard"], [4], 100), Mode.PRACTICE)

    assert sorted(a.question_id for a in attempt.answers) == sorted(easy_ids)


def test_questions_index_lists_chapters_with_counts(client: TestClient) -> None:
    page = client.get("/domande").text

    assert 'href="/domande/1"' in page
    assert "Capitolo 1" in page
    assert 'level-hard"></span>10<' in page


def test_chapter_page_filters_by_level(client: TestClient) -> None:
    every = client.get("/domande/1").text
    hard = client.get("/domande/1", params={"level": "hard"}).text

    assert every.count('class="question-row"') == 40
    assert hard.count('class="question-row"') == 10
    assert hard.count('class="panel topic"') == 10


def test_chapter_page_shows_shared_figures_once_and_single_ones_inline(client: TestClient) -> None:
    page = client.get("/domande/1").text

    assert "Quesito 4001" in page
    assert page.count('class="topic-figure"') == 5
    assert page.count('class="inline-figure"') == 5
    assert "Capitolo 1; titolo completo" in page


def test_practice_page_names_chapter_and_quesito(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 1)
    topic_id = _attempt(app, attempt_id, Mode.PRACTICE).answers[0].question.topic_id

    page = client.get(f"/esercitazione/{attempt_id}").text

    assert f"Capitolo 1 &middot; Quesito {topic_id}" in page


def test_history_lists_only_completed_attempts(client: TestClient, app: FastAPI) -> None:
    exam_id = _start_exam(client, ALL_LEVELS)
    client.post(f"/esame/{exam_id}")
    completed_id = _complete_practice(client, app)
    interrupted_id = _start_practice(client, ALL_LEVELS, [1], 3)
    _answer(client, f"/esercitazione/{interrupted_id}/risposte", 1, True)
    client.post(f"/esercitazione/{interrupted_id}/fine")
    _start_practice(client, ALL_LEVELS, [1], 3)

    page = client.get("/storico").text

    assert page.count("<tr>") == 3
    assert f"/esame/{exam_id}/risultato" in page
    assert f"/esercitazione/{completed_id}/riepilogo" in page
    assert f"/esercitazione/{interrupted_id}/riepilogo" not in page


def test_history_chart_points_are_oldest_first(
    client: TestClient, app: FastAPI, clock: Clock
) -> None:
    practice_id = _complete_practice(client, app)
    clock.advance(timedelta(minutes=5))
    exam_id = _start_exam(client, ALL_LEVELS)
    client.post(f"/esame/{exam_id}")

    page = client.get("/storico").text
    raw = page.split("data-chart-points>", 1)[1].split("</script>", 1)[0]
    points = json.loads(raw)

    assert [point["mode"] for point in points] == ["practice", "exam"]
    assert points[0]["url"] == f"/esercitazione/{practice_id}/riepilogo"
    assert points[0]["percent"] == 100
    assert points[1]["correct"] == 0


def test_history_keeps_the_levels_of_finished_attempts(client: TestClient, app: FastAPI) -> None:
    attempt_id = _complete_practice(client, app)
    attempt = _attempt(app, attempt_id, Mode.PRACTICE)
    counts = {level: sum(a.question.level == level for a in attempt.answers) for level in Level}
    for answer in attempt.answers:
        client.post(f"/api/questions/{answer.question_id}/level", json={"level": "hard"})

    page = client.get("/storico").text

    assert _attempt(app, attempt_id, Mode.PRACTICE).level_counts == counts
    assert page.count('class="mini-bar"') == 1
    assert f'title="Difficile: {counts[Level.HARD]}"' in page


def test_history_without_attempts_invites_to_start(client: TestClient) -> None:
    page = client.get("/storico").text

    assert "data-chart" not in page
    assert 'href="/esame"' in page


def test_interrupted_practice_summary_says_so(client: TestClient) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)

    response = client.post(f"/esercitazione/{attempt_id}/fine")

    assert "Esercitazione interrotta" in response.text


def test_completed_practice_summary_says_so(client: TestClient, app: FastAPI) -> None:
    attempt_id = _complete_practice(client, app)

    page = client.get(f"/esercitazione/{attempt_id}/riepilogo").text

    assert "Esercitazione completata" in page


def test_revealed_question_counts_as_done_but_wrong(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 2)
    first, _ = _attempt(app, attempt_id, Mode.PRACTICE).answers
    _reveal(client, attempt_id, 1)
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 2, True)

    response = client.post(f"/esercitazione/{attempt_id}/fine")

    assert "Esercitazione completata" in response.text
    assert "1 rivelate" in response.text
    assert _attempt(app, attempt_id, Mode.PRACTICE).answers[0].is_correct is False
    assert first.revealed is False


@pytest.mark.parametrize(("first", "then"), [("reveal", "answer"), ("answer", "reveal")])
def test_reveal_and_answer_exclude_each_other(client: TestClient, first: str, then: str) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 2)
    actions = {
        "reveal": lambda: client.post(f"/esercitazione/{attempt_id}/rivela", json={"position": 1}),
        "answer": lambda: client.post(
            f"/esercitazione/{attempt_id}/risposte", json={"position": 1, "given": True}
        ),
    }

    assert actions[first]().status_code == 204
    assert actions[then]().status_code == 409


def test_reveal_unknown_position_is_404(client: TestClient) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 2)

    response = client.post(f"/esercitazione/{attempt_id}/rivela", json={"position": 9})

    assert response.status_code == 404


def test_answering_or_revealing_marks_questions_as_seen(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 1, True)
    _reveal(client, attempt_id, 2)

    answers = _attempt(app, attempt_id, Mode.PRACTICE).answers

    assert [answer.question.seen for answer in answers] == [True, True, False]


def test_unseen_only_practice_skips_seen_questions(client: TestClient, app: FastAPI) -> None:
    _mark_seen(app, [Level.EASY])

    attempt_id = _start_practice_with(
        client, _practice_form(ALL_LEVELS, [1], 100) | {"unseen_only": "true"}
    )

    answers = _attempt(app, attempt_id, Mode.PRACTICE).answers
    assert len(answers) == 30
    assert Level.EASY not in {answer.question.level for answer in answers}


def test_unseen_only_exam_skips_seen_questions(client: TestClient, app: FastAPI) -> None:
    _mark_seen(app, [Level.EASY])

    response = client.post(
        "/esame", data={"level": ALL_LEVELS, "unseen_only": "true"}, follow_redirects=False
    )
    attempt_id = int(response.headers["location"].rsplit("/", 1)[1])

    answers = _attempt(app, attempt_id, Mode.EXAM).answers
    assert Level.EASY not in {answer.question.level for answer in answers}


def test_unseen_only_exam_needs_enough_unseen_topics(client: TestClient, app: FastAPI) -> None:
    _mark_seen(app, [Level.EASY, Level.MEDIUM])

    response = client.post("/esame", data={"level": ALL_LEVELS, "unseen_only": "true"})

    assert response.status_code == 400
    assert "argomenti diversi" in response.text
    assert 'name="unseen_only" value="true" checked' in response.text


def test_home_shows_seen_questions_by_current_level(client: TestClient, app: FastAPI) -> None:
    attempt_id = _start_practice(client, ["easy"], [1], 1)
    question_id = _attempt(app, attempt_id, Mode.PRACTICE).answers[0].question_id
    _answer(client, f"/esercitazione/{attempt_id}/risposte", 1, True)

    before = client.get("/").text
    client.post(f"/api/questions/{question_id}/level", json={"level": "hard"})
    after = client.get("/").text

    assert 'title="Tutte: 1 di 160 viste"' in before
    assert "0,6%" in before
    assert 'title="Facile: 1 di 70 viste"' in before
    assert 'title="Difficile: 0 di 10 viste"' in before
    assert 'title="Facile: 0 di 69 viste"' in after
    assert 'title="Difficile: 1 di 11 viste"' in after


def test_home_shows_exam_stats(client: TestClient, app: FastAPI) -> None:
    assert "Nessuno ancora" in client.get("/").text
    attempt_id = _start_exam(client, ALL_LEVELS)
    for item in _attempt(app, attempt_id, Mode.EXAM).answers:
        _answer(client, f"/esame/{attempt_id}/risposte", item.position, item.question.answer)
    client.post(f"/esame/{attempt_id}")

    page = client.get("/").text

    assert "Promosso" in page
    assert "1<small>su 1</small>" in page


def test_exam_setup_shows_level_totals(client: TestClient) -> None:
    page = client.get("/esame").text

    assert "<small>10</small>" in page


def _start_exam(client: TestClient, levels: list[str]) -> int:
    response = client.post("/esame", data={"level": levels}, follow_redirects=False)
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[1])


def _start_practice(client: TestClient, levels: list[str], chapters: list[int], count: int) -> int:
    form = _practice_form(levels, chapters, count) | {"instant_feedback": "true"}
    return _start_practice_with(client, form)


def _start_blind_practice(client: TestClient, chapters: list[int], count: int) -> int:
    return _start_practice_with(client, _practice_form(ALL_LEVELS, chapters, count))


def _start_practice_with(client: TestClient, form: dict[str, Any]) -> int:
    response = client.post("/esercitazione", data=form, follow_redirects=False)
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[1])


def _practice_form(levels: list[str], chapters: list[int], count: int) -> dict[str, Any]:
    return {"level": levels, "chapter": [str(c) for c in chapters], "count": str(count)}


def _complete_practice(client: TestClient, app: FastAPI) -> int:
    attempt_id = _start_practice(client, ALL_LEVELS, [1], 3)
    for item in _attempt(app, attempt_id, Mode.PRACTICE).answers:
        url = f"/esercitazione/{attempt_id}/risposte"
        _answer(client, url, item.position, item.question.answer)
    client.post(f"/esercitazione/{attempt_id}/fine")
    return attempt_id


def _reveal(client: TestClient, attempt_id: int, position: int) -> None:
    response = client.post(f"/esercitazione/{attempt_id}/rivela", json={"position": position})
    assert response.status_code == 204


def _answer(client: TestClient, url: str, position: int, given: bool) -> None:
    response = client.post(url, json={"position": position, "given": given})
    assert response.status_code == 204


def _attempt(app: FastAPI, attempt_id: int, mode: Mode) -> Attempt:
    with Session(app.state.engine, expire_on_commit=False) as session:
        attempt = store.get_attempt(session, attempt_id, mode)
        for answer in attempt.answers:
            _ = answer.question.topic.chapter.title
        return attempt


def _mark_seen(app: FastAPI, levels: list[Level]) -> None:
    with Session(app.state.engine) as session:
        for question in session.exec(select(Question).where(col(Question.level).in_(levels))):
            question.seen = True
            session.add(question)
        session.commit()


def _question(app: FastAPI, question_id: int) -> Question:
    with Session(app.state.engine) as session:
        question = session.get(Question, question_id)
        assert question is not None
        return question
