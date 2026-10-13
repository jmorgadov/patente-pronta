# patente-pronta data

Question bank for the Italian driving licence theory exam (patente A/B), extracted from the
ministry's official list of true/false quiz questions. The exam is 30 true/false questions
drawn from this bank; passing needs at most 3 errors.

## Source and license

`quiz-AB.pdf` is the "Patente AB" (conseguimento) list published by the Ministero delle
Infrastrutture e dei Trasporti on the [Portale dell'Automobilista](https://www.ilportaledellautomobilista.it/web/portale-automobilista/-/quiz-per-le-patenti-am-b-superiori-e-cqc)
(original file name `210926_Conseguimento A-B italiano.pdf`). The ministry releases it under
[CC BY 3.0 IT](https://creativecommons.org/licenses/by/3.0/it/) ([legal notes](https://www.mit.gov.it/note-legali)).
`quiz.json` and `figures/` are adapted from it and shared under the same license. Unlike the
code, nothing in this directory is under the MIT License: see [`LICENSE`](LICENSE) for the
full attribution and the list of changes.

## Files

| Path | What it is |
|---|---|
| `quiz-AB.pdf` | Source PDF (586 pages). Do not read it directly — use `quiz.json`. |
| `quiz.json` | All questions, structured, each with its starting level (~2 MB). |
| `figures/*.jpg` | Figures (road signs, intersections, warning lights) referenced by the questions. |
| `LICENSE` | Source, license (CC BY 3.0 IT) and changes for the files in this directory. |
| `../scripts/extract_quiz.py` | Regenerates `quiz.json` and `figures/` from the PDF. |

`quiz.json` is too large to read whole: load it with Python and query it (`jq` is not
installed).

## quiz.json

```
{
  "source": "quiz-AB.pdf",
  "figures": { "<key>": "figures/<key>.jpg", ... },       // key = first 12 hex of the JPEG's sha256
  "chapters": [
    { "id": 2,                                             // 1..25, in quesito-number order
      "title": "Segnali di pericolo",                      // our own short name
      "full_title": "Segnali di pericolo",                 // the PDF's title, abbreviations included
      "quesiti": [
        { "id": 4051,                                      // official quesito number
          "questions": [
            { "id": 18850,                                 // official question number, unique
              "q": "Il segnale raffigurato preannuncia un tratto di strada deformata",
              "answer": true,
              "figures": ["b36277fdfc44"],                 // keys into "figures", may be []
              "level": "easy" } ] } ] } ]                  // easy | medium | hard
}
```

- 25 chapters → 715 quesiti → 7,020 questions (3,524 true, 3,496 false).
- Chapters are the 25 topics of the ministry's exam programme, taken from the PDF's
  "Quesito n° N - <title>" headers. The PDF shuffles the quesiti, but each chapter covers a
  contiguous range of quesito numbers (4001–4716).
- Within a quesito, questions are in PDF order: true ones first. The app shuffles them.
- Every question in the PDF has at most one figure; `figures` is a list so that a question
  could have several. 3,919 questions have a figure; there are 407 distinct images. Several
  combine panels labelled A and B, which the question text refers to.
- Text is copied as-is, except that lines are joined and the PDF's "¿" (a broken apostrophe)
  is replaced with "'".

## Levels

Levels were assigned with AI, reading each question, calibrated for a learner who is almost
ready for the exam:

- **easy:** common sense or the basic meaning of a sign; false statements are absurd.
- **medium:** needs a standard but commonly known rule.
- **hard:** specific numbers (distances, speeds, masses, ages, points, durations), exceptions,
  one-word traps (solo/sempre/anche), rare signs/panels, intersection ordering from a figure,
  or counter-intuitive rules.

These are not official data. They are only starting points: the learner can change any of
them in the app, and the change is stored in their database, not here. Counts: 3,276 easy,
2,737 medium, 1,007 hard.

## Regenerating

From the repository root:

```
uv run scripts/extract_quiz.py
```

This takes about 3 s and rewrites `quiz.json` and adds any new images to `figures/`. Levels
already in `quiz.json` are kept, matched by question id. New questions get `"level": null`
and the script reports them as an issue; give them a level before loading the bank.
