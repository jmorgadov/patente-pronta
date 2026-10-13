import random
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from patente_pronta import store
from patente_pronta.errors import NotEnoughQuestionsError
from patente_pronta.models import (
    AnswerIn,
    Attempt,
    ExamSettings,
    Level,
    LevelIn,
    LevelOut,
    Mode,
    PracticeSettings,
    Question,
    RevealIn,
)
from patente_pronta.quiz import EXAM_DURATION, EXAM_PASS_MARK, EXAM_SIZE, is_passed

PACKAGE_DIR = Path(__file__).parent
LEVEL_LABELS = {Level.EASY: "Facile", Level.MEDIUM: "Media", Level.HARD: "Difficile"}
EXAM_SETTINGS_COOKIE = "exam_settings"
PRACTICE_SETTINGS_COOKIE = "practice_settings"
SETTINGS_MAX_AGE = 365 * 24 * 60 * 60
DEFAULT_EXAM_SETTINGS = ExamSettings(levels=list(Level), unseen_only=False)
DEFAULT_PRACTICE_SETTINGS = PracticeSettings(
    levels=list(Level), chapters=None, count=30, unseen_only=False, instant_feedback=True
)

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
templates.env.globals.update(
    LEVELS=list(Level),
    LEVEL_LABELS=LEVEL_LABELS,
    EXAM_SIZE=EXAM_SIZE,
    EXAM_PASS_MARK=EXAM_PASS_MARK,
    EXAM_MINUTES=int(EXAM_DURATION.total_seconds() // 60),
)

templates.env.filters["it_number"] = lambda value: f"{value:,}".replace(",", ".")
templates.env.filters["it_percent"] = lambda value: f"{value:.1f}".replace(".", ",")

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_rng() -> random.Random:
    return random.SystemRandom()


def get_now() -> datetime:
    return datetime.now(UTC)


SessionDep = Annotated[Session, Depends(get_session)]
RngDep = Annotated[random.Random, Depends(get_rng)]
NowDep = Annotated[datetime, Depends(get_now)]
LevelsForm = Annotated[list[Level], Form(alias="level", default_factory=list)]
CheckboxForm = Annotated[bool, Form(default_factory=bool)]


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep) -> HTMLResponse:
    attempts = store.completed_attempts(session)
    exams = [attempt for attempt in attempts if attempt.mode == Mode.EXAM]
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "level_totals": store.level_totals(session),
            "seen_totals": store.seen_totals(session),
            "last_exam": exams[-1] if exams else None,
            "exams_taken": len(exams),
            "exams_passed": sum(is_passed(exam.correct or 0) for exam in exams),
            "practices_completed": len(attempts) - len(exams),
        },
    )


@router.get("/esame", response_class=HTMLResponse)
def exam_setup(request: Request, session: SessionDep) -> HTMLResponse:
    settings = _saved(request, EXAM_SETTINGS_COOKIE, ExamSettings, DEFAULT_EXAM_SETTINGS)
    return _exam_setup(request, session, settings, None)


@router.post("/esame", response_model=None)
def exam_start(
    request: Request,
    session: SessionDep,
    rng: RngDep,
    now: NowDep,
    levels: LevelsForm,
    unseen_only: CheckboxForm,
) -> Response:
    settings = ExamSettings(levels=levels, unseen_only=unseen_only)
    if not levels:
        return _exam_setup(request, session, settings, "Seleziona almeno un livello")
    try:
        attempt = store.start_exam(session, levels, unseen_only, rng, now)
    except NotEnoughQuestionsError as err:
        return _exam_setup(request, session, settings, str(err))
    return _redirect_saving(f"/esame/{attempt.id}", EXAM_SETTINGS_COOKIE, settings)


@router.get("/esame/{attempt_id}", response_model=None)
def exam_page(request: Request, session: SessionDep, now: NowDep, attempt_id: int) -> Response:
    attempt = _attempt(session, attempt_id, Mode.EXAM)
    if attempt.finished_at is not None or store.is_expired(attempt, now):
        store.finish(session, attempt, now)
        return RedirectResponse(f"/esame/{attempt_id}/risultato", status_code=303)
    return templates.TemplateResponse(
        request,
        "exam.html",
        {"attempt": attempt, "remaining_seconds": store.remaining_seconds(attempt, now)},
    )


@router.post("/esame/{attempt_id}/risposte", status_code=204)
def exam_answer(session: SessionDep, now: NowDep, attempt_id: int, answer: AnswerIn) -> None:
    _record(session, _attempt(session, attempt_id, Mode.EXAM), answer, now)


@router.post("/esame/{attempt_id}")
def exam_submit(session: SessionDep, now: NowDep, attempt_id: int) -> RedirectResponse:
    store.finish(session, _attempt(session, attempt_id, Mode.EXAM), now)
    return RedirectResponse(f"/esame/{attempt_id}/risultato", status_code=303)


@router.get("/esame/{attempt_id}/risultato", response_model=None)
def exam_result(request: Request, session: SessionDep, now: NowDep, attempt_id: int) -> Response:
    attempt = _attempt(session, attempt_id, Mode.EXAM)
    if attempt.finished_at is None:
        if not store.is_expired(attempt, now):
            return RedirectResponse(f"/esame/{attempt_id}", status_code=303)
        store.finish(session, attempt, now)
    return _review(request, attempt)


@router.get("/esercitazione", response_class=HTMLResponse)
def practice_setup(request: Request, session: SessionDep) -> HTMLResponse:
    settings = _saved(
        request, PRACTICE_SETTINGS_COOKIE, PracticeSettings, DEFAULT_PRACTICE_SETTINGS
    )
    return _practice_setup(request, session, settings, None)


@router.post("/esercitazione", response_model=None)
def practice_start(
    request: Request,
    session: SessionDep,
    rng: RngDep,
    now: NowDep,
    levels: LevelsForm,
    chapters: Annotated[list[int], Form(alias="chapter", default_factory=list)],
    count: Annotated[int, Form(ge=1, le=1000)],
    unseen_only: CheckboxForm,
    instant_feedback: CheckboxForm,
) -> Response:
    settings = PracticeSettings(
        levels=levels,
        chapters=chapters,
        count=count,
        unseen_only=unseen_only,
        instant_feedback=instant_feedback,
    )
    error = None
    if not levels:
        error = "Seleziona almeno un livello"
    elif not chapters:
        error = "Seleziona almeno un capitolo"
    else:
        try:
            attempt = store.start_practice(
                session, levels, chapters, count, unseen_only, instant_feedback, rng, now
            )
        except NotEnoughQuestionsError as err:
            error = str(err)
        else:
            url = f"/esercitazione/{attempt.id}"
            return _redirect_saving(url, PRACTICE_SETTINGS_COOKIE, settings)
    return _practice_setup(request, session, settings, error)


@router.get("/esercitazione/{attempt_id}", response_model=None)
def practice_page(request: Request, session: SessionDep, attempt_id: int) -> Response:
    attempt = _attempt(session, attempt_id, Mode.PRACTICE)
    if attempt.finished_at is not None:
        return RedirectResponse(f"/esercitazione/{attempt_id}/riepilogo", status_code=303)
    return templates.TemplateResponse(request, "practice.html", {"attempt": attempt})


@router.post("/esercitazione/{attempt_id}/risposte", status_code=204)
def practice_answer(session: SessionDep, now: NowDep, attempt_id: int, answer: AnswerIn) -> None:
    _record(session, _attempt(session, attempt_id, Mode.PRACTICE), answer, now)


@router.post("/esercitazione/{attempt_id}/rivela", status_code=204)
def practice_reveal(session: SessionDep, now: NowDep, attempt_id: int, reveal: RevealIn) -> None:
    attempt = _attempt(session, attempt_id, Mode.PRACTICE)
    try:
        store.reveal_answer(session, attempt, reveal.position, now)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err


@router.post("/esercitazione/{attempt_id}/fine")
def practice_finish(session: SessionDep, now: NowDep, attempt_id: int) -> RedirectResponse:
    store.finish(session, _attempt(session, attempt_id, Mode.PRACTICE), now)
    return RedirectResponse(f"/esercitazione/{attempt_id}/riepilogo", status_code=303)


@router.get("/esercitazione/{attempt_id}/riepilogo", response_model=None)
def practice_summary(request: Request, session: SessionDep, attempt_id: int) -> Response:
    attempt = _attempt(session, attempt_id, Mode.PRACTICE)
    if attempt.finished_at is None:
        return RedirectResponse(f"/esercitazione/{attempt_id}", status_code=303)
    return _review(request, attempt)


@router.get("/domande", response_class=HTMLResponse)
def questions_index(request: Request, session: SessionDep) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "questions_index.html",
        {"chapters": store.chapters(session), "counts": store.level_counts_by_chapter(session)},
    )


@router.get("/domande/{chapter_id}", response_class=HTMLResponse)
def questions_chapter(
    request: Request,
    session: SessionDep,
    chapter_id: int,
    levels: Annotated[list[Level], Query(alias="level", default_factory=list)],
) -> HTMLResponse:
    try:
        chapter = store.chapter(session, chapter_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    shown = levels or list(Level)
    topics = [(topic, [q for q in topic.questions if q.level in shown]) for topic in chapter.topics]
    return templates.TemplateResponse(
        request,
        "questions_chapter.html",
        {
            "chapter": chapter,
            "topics": [(topic, questions) for topic, questions in topics if questions],
            "selected_levels": shown,
        },
    )


@router.get("/storico", response_class=HTMLResponse)
def history(request: Request, session: SessionDep) -> HTMLResponse:
    attempts = store.completed_attempts(session)
    return templates.TemplateResponse(
        request, "history.html", {"points": [_progress_point(attempt) for attempt in attempts]}
    )


@router.post("/api/questions/{question_id}/level")
def question_set_level(session: SessionDep, question_id: int, body: LevelIn) -> LevelOut:
    try:
        return _level_out(store.set_level(session, question_id, body.level))
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/api/questions/{question_id}/level/reset")
def question_reset_level(session: SessionDep, question_id: int) -> LevelOut:
    try:
        return _level_out(store.reset_level(session, question_id))
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


def _exam_setup(
    request: Request, session: Session, settings: ExamSettings, error: str | None
) -> HTMLResponse:
    context: dict[str, Any] = {
        "selected_levels": settings.levels,
        "unseen_only": settings.unseen_only,
        "error": error,
        "level_totals": store.level_totals(session),
    }
    return templates.TemplateResponse(
        request, "exam_setup.html", context, status_code=400 if error else 200
    )


def _practice_setup(
    request: Request, session: Session, settings: PracticeSettings, error: str | None
) -> HTMLResponse:
    context: dict[str, Any] = {
        "chapters": store.chapters(session),
        "selected_levels": settings.levels,
        "selected_chapters": settings.chapters,
        "count": settings.count,
        "unseen_only": settings.unseen_only,
        "instant_feedback": settings.instant_feedback,
        "error": error,
    }
    return templates.TemplateResponse(
        request, "practice_setup.html", context, status_code=400 if error else 200
    )


def _saved[S: BaseModel](request: Request, cookie: str, model: type[S], default: S) -> S:
    raw = request.cookies.get(cookie)
    if raw is None:
        return default
    try:
        return model.model_validate_json(raw)
    except ValidationError:
        return default


def _redirect_saving(url: str, cookie: str, settings: BaseModel) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        cookie, settings.model_dump_json(), max_age=SETTINGS_MAX_AGE, httponly=True, samesite="lax"
    )
    return response


def _review(request: Request, attempt: Attempt) -> HTMLResponse:
    answers = sorted(attempt.answers, key=lambda a: (a.is_correct, a.position))
    correct = attempt.correct or 0
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "attempt": attempt,
            "answers": answers,
            "correct": correct,
            "wrong": sum(a.given is not None and not a.is_correct for a in answers),
            "revealed": sum(a.revealed for a in answers),
            "unanswered": sum(not a.is_done for a in answers),
            "passed": is_passed(correct),
        },
    )


def _progress_point(attempt: Attempt) -> dict[str, Any]:
    correct = attempt.correct or 0
    total = len(attempt.answers)
    finished_at = attempt.finished_at or attempt.started_at
    return {
        "mode": attempt.mode.value,
        "date": finished_at.astimezone().strftime("%d/%m/%Y %H:%M"),
        "correct": correct,
        "total": total,
        "percent": round(100 * correct / total, 1) if total else 0,
        "passed": is_passed(correct),
        "level_counts": attempt.level_counts,
        "url": _review_url(attempt),
    }


def _review_url(attempt: Attempt) -> str:
    if attempt.mode == Mode.EXAM:
        return f"/esame/{attempt.id}/risultato"
    return f"/esercitazione/{attempt.id}/riepilogo"


def _attempt(session: Session, attempt_id: int, mode: Mode) -> Attempt:
    try:
        return store.get_attempt(session, attempt_id, mode)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


def _record(session: Session, attempt: Attempt, answer: AnswerIn, now: datetime) -> None:
    try:
        store.record_answer(session, attempt, answer.position, answer.given, now)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err


def _level_out(question: Question) -> LevelOut:
    return LevelOut(level=question.level, default_level=question.default_level)
