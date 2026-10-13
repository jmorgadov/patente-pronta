# /// script
# requires-python = ">=3.13"
# dependencies = ["pymupdf"]
# ///
"""Extract the question bank and its figures from the ministry's quiz PDF.

Run from the repository root:  uv run scripts/extract_quiz.py

Output:
  data/quiz.json        chapters -> quesiti -> questions
  data/figures/*.jpg    one JPEG per distinct figure, named by a hash of its bytes

Levels already in data/quiz.json are kept, matched by question id.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import pymupdf

DATA_DIR = Path("data")
PDF = DATA_DIR / "quiz-AB.pdf"
OUT_JSON = DATA_DIR / "quiz.json"
FIG_DIR = DATA_DIR / "figures"

HEADER_RE = re.compile(r"^Quesito n° (\d+) - (.*)$")
TABLE_HEADINGS = {"Numero", "domanda", "Testo domanda", "Risposta Corretta", "Immagine"}
PAGE_TITLE = "Ministero delle Infrastrutture e dei Trasporti"
ANSWERS = {"VERO": True, "FALSO": False}

HEADER_MAX_X = 21  # quesito headers start at x=20, question numbers at x=22
NUMBER_MAX_X = 40
TEXT_MAX_X = 350  # the answer column starts at x=355
ANSWER_MAX_X = 420
FIGURE_MIN_X = 420
ROW_TOLERANCE = 3
FIGURE_TOLERANCE = 4

# Short names for the 25 chapters, keyed by the start of the PDF's full title.
CHAPTER_NAMES = {
    "Definizioni stradali e di traffico": "Definizioni stradali e doveri del conducente",
    "Segnali di pericolo": "Segnali di pericolo",
    "Segnali di divieto": "Segnali di divieto",
    "Segnali di obbligo": "Segnali di obbligo",
    "Segnali di precedenza": "Segnali di precedenza",
    "Segnaletica orizzontale": "Segnaletica orizzontale e segni sugli ostacoli",
    "Segnalazioni semaforiche": "Semafori e segnalazioni degli agenti",
    "Segnali di indicazione": "Segnali di indicazione",
    "Segnali complementari": "Segnali complementari, temporanei e di cantiere",
    "Pannelli integrativi": "Pannelli integrativi",
    "Limiti di velocità": "Velocità, intralcio e passaggi a livello",
    "Distanza di sicurezza": "Distanza di sicurezza",
    "Norme sulla circol.": "Circolazione, svolta e norme di precedenza",
    "Esempi di precedenza": "Precedenza agli incroci",
    "Norme sul sorpasso": "Sorpasso",
    "Fermata, sosta": "Fermata, sosta, arresto e partenza",
    "Ingombro della carreggiata": "Veicolo fermo, autostrade, carico e traino",
    "Uso delle luci": "Luci, dispositivi acustici e spie",
    "Dispositivi di equipaggiamento": "Equipaggiamento, cinture e casco",
    "Patenti di guida": "Patente, documenti e sanzioni",
    "Comportamenti per prevenire": "Incidenti stradali",
    "Guida in relazione": "Condizioni fisiche, alcol, droghe e primo soccorso",
    "Responsabilità civile": "Responsabilità e assicurazione",
    "Limitazione dei consumi": "Consumi e ambiente",
    "Elementi costitutivi del veicolo": "Veicolo, manutenzione e tenuta di strada",
}


class QuestionOut(TypedDict):
    id: int
    q: str
    answer: bool
    figures: list[str]
    level: str | None


class QuesitoOut(TypedDict):
    id: int
    questions: list[QuestionOut]


class ChapterOut(TypedDict):
    id: int
    title: str
    full_title: str
    quesiti: list[QuesitoOut]


@dataclass
class Row:
    number: int
    page: int
    y: float
    text: list[str] = field(default_factory=list)
    answer: bool | None = None
    figures: list[str] = field(default_factory=list)


@dataclass
class Quesito:
    number: int
    title: list[str]
    rows: list[Row] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Line:
    page: int
    x: float
    y: float
    text: str


@dataclass(frozen=True, slots=True)
class Placement:
    page: int
    y: float
    xref: int


def main() -> int:
    doc = pymupdf.open(PDF)
    FIG_DIR.mkdir(exist_ok=True)
    figures = save_figures(doc)
    quesiti = parse(doc, figures)
    levels = known_levels()
    chapters = build_chapters(quesiti, levels)
    issues = check(quesiti, levels)

    out = {
        "source": PDF.name,
        "figures": {key: f"figures/{key}.jpg" for key in sorted(set(figures.values()))},
        "chapters": chapters,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")

    questions = [row for quesito in quesiti for row in quesito.rows]
    print(
        f"chapters={len(chapters)} quesiti={len(quesiti)} questions={len(questions)} "
        f"true={sum(bool(row.answer) for row in questions)} "
        f"with_figure={sum(bool(row.figures) for row in questions)} "
        f"figures={len(out['figures'])}"
    )
    for issue in issues:
        print("issue:", issue)
    return 1 if issues else 0


def save_figures(doc: pymupdf.Document) -> dict[int, str]:
    """Write every distinct figure once; return xref -> figure key."""
    keys: dict[int, str] = {}
    for page in doc:
        for info in page.get_image_info(xrefs=True):
            xref = info["xref"]
            if info["bbox"][0] < FIGURE_MIN_X or xref in keys:
                continue
            image = doc.extract_image(xref)
            data: bytes = image["image"]
            if image["ext"] != "jpeg":
                raise ValueError(f"p{page.number + 1}: figure {xref} is {image['ext']}, not jpeg")
            key = hashlib.sha256(data).hexdigest()[:12]
            path = FIG_DIR / f"{key}.jpg"
            if not path.exists():
                path.write_bytes(data)
            keys[xref] = key
    return keys


def parse(doc: pymupdf.Document, figures: dict[int, str]) -> list[Quesito]:
    quesiti: list[Quesito] = []
    in_header = False
    for page in doc:
        rows: list[Row] = []
        for line in page_lines(page):
            if (match := HEADER_RE.match(line.text)) is not None:
                quesiti.append(Quesito(number=int(match.group(1)), title=[match.group(2)]))
                in_header = True
            elif line.x < HEADER_MAX_X and in_header:
                quesiti[-1].title.append(line.text)
            elif line.text in TABLE_HEADINGS:
                in_header = False
            elif line.text == PAGE_TITLE:
                continue
            elif line.x < NUMBER_MAX_X and line.text.isdigit():
                in_header = False
                rows.append(Row(number=int(line.text), page=line.page, y=line.y))
                quesiti[-1].rows.append(rows[-1])
            elif line.x < TEXT_MAX_X and rows:
                rows[-1].text.append(line.text)
            elif line.x < ANSWER_MAX_X and line.text in ANSWERS and rows:
                rows[-1].answer = ANSWERS[line.text]
            else:
                raise ValueError(f"p{line.page}: unexpected line {line.text!r} at x={line.x:.0f}")
        attach_figures(page_placements(page), rows, figures)
    return quesiti


def page_lines(page: pymupdf.Page) -> list[Line]:
    """Return the page's text runs in reading order, split at column boundaries."""
    raw: list[tuple[float, float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    raw.append((span["bbox"][1], span["bbox"][0], span["text"]))
    raw.sort()
    rows: list[list[tuple[float, float, str]]] = []
    for y, x, text in raw:
        if rows and y - rows[-1][0][0] <= ROW_TOLERANCE:
            rows[-1].append((y, x, text))
        else:
            rows.append([(y, x, text)])
    lines: list[Line] = []
    for row in rows:
        lines.extend(merge_columns(page.number + 1, sorted(row, key=lambda item: item[1])))
    return lines


def merge_columns(page: int, row: list[tuple[float, float, str]]) -> list[Line]:
    """Join the spans of one visual row that belong to the same column."""
    merged: list[Line] = []
    for y, x, text in row:
        if merged and column(merged[-1].x) == column(x):
            last = merged.pop()
            merged.append(Line(page, last.x, last.y, last.text + text))
        else:
            merged.append(Line(page, x, y, text))
    return [Line(ln.page, ln.x, ln.y, " ".join(ln.text.split())) for ln in merged]


def column(x: float) -> int:
    return sum(x >= edge for edge in (NUMBER_MAX_X, TEXT_MAX_X, ANSWER_MAX_X))


def page_placements(page: pymupdf.Page) -> list[Placement]:
    return [
        Placement(page=page.number + 1, y=info["bbox"][1], xref=info["xref"])
        for info in page.get_image_info(xrefs=True)
        if info["bbox"][0] >= FIGURE_MIN_X
    ]


def attach_figures(placements: list[Placement], rows: list[Row], figures: dict[int, str]) -> None:
    for placement in placements:
        above = [row for row in rows if row.y <= placement.y + FIGURE_TOLERANCE]
        if not above:
            raise ValueError(f"p{placement.page}: figure at y={placement.y:.0f} has no question")
        row = max(above, key=lambda row: row.y)
        key = figures[placement.xref]
        if key not in row.figures:
            row.figures.append(key)


def known_levels() -> dict[int, str]:
    if not OUT_JSON.exists():
        return {}
    previous: dict[str, Any] = json.loads(OUT_JSON.read_text())
    return {
        question["id"]: question["level"]
        for chapter in previous["chapters"]
        for quesito in chapter["quesiti"]
        for question in quesito["questions"]
        if question.get("level")
    }


def build_chapters(quesiti: list[Quesito], levels: dict[int, str]) -> list[ChapterOut]:
    chapters: dict[str, ChapterOut] = {}
    for quesito in sorted(quesiti, key=lambda q: q.number):
        full_title = clean(" ".join(quesito.title))
        if full_title not in chapters:
            chapters[full_title] = {
                "id": len(chapters) + 1,
                "title": short_title(full_title),
                "full_title": full_title,
                "quesiti": [],
            }
        chapters[full_title]["quesiti"].append(
            {
                "id": quesito.number,
                "questions": [
                    {
                        "id": row.number,
                        "q": clean(join_lines(row.text)),
                        "answer": bool(row.answer),
                        "figures": row.figures,
                        "level": levels.get(row.number),
                    }
                    for row in quesito.rows
                ],
            }
        )
    return list(chapters.values())


def short_title(full_title: str) -> str:
    for prefix, name in CHAPTER_NAMES.items():
        if full_title.startswith(prefix):
            return name
    raise ValueError(f"No short name for chapter {full_title!r}")


def join_lines(lines: list[str]) -> str:
    # Lines only break after a hyphen inside compounds ("air-bag"), so the hyphen stays.
    joined = lines[0]
    for line in lines[1:]:
        joined += line if joined.endswith("-") else f" {line}"
    return joined


def clean(text: str) -> str:
    # The PDF encodes some apostrophes as an inverted question mark.
    return " ".join(text.replace("¿", "'").split())


def check(quesiti: list[Quesito], levels: dict[int, str]) -> list[str]:
    issues: list[str] = []
    numbers = [row.number for quesito in quesiti for row in quesito.rows]
    if len(numbers) != len(set(numbers)):
        issues.append("question numbers are not unique")
    if len({q.number for q in quesiti}) != len(quesiti):
        issues.append("quesito numbers are not unique")
    for quesito in quesiti:
        if not quesito.rows:
            issues.append(f"quesito {quesito.number}: no questions")
        for row in quesito.rows:
            if row.answer is None:
                issues.append(f"question {row.number} (p{row.page}): no answer")
            if not row.text:
                issues.append(f"question {row.number} (p{row.page}): no text")
    if levels:
        missing = [number for number in numbers if number not in levels]
        if missing:
            issues.append(f"{len(missing)} questions have no level, e.g. {missing[:5]}")
    return issues


if __name__ == "__main__":
    sys.exit(main())
