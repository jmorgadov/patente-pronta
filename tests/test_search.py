import pytest

from patente_pronta.search import Segment, highlight, rank

TEXTS = {
    1: "Il sorpasso è vietato in curva",
    2: "In autostrada il limite è di 130 km/h",
    3: "Con la nebbia si accendono i fendinebbia",
    4: "Il sorpasso a destra è consentito al tram",
    5: "Nei centri abitati il limite è di 50 km/h",
}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("sorpasso curva", [1]),
        ("SORPASSO", [1, 4]),
        ("sorpaso", [1, 4]),
        ("autostrade", [2]),
        ("velocità", []),
        ("vietato", [1]),
        ("130", [2]),
        ("13", []),
        ("nebbia", [3]),
        ("limite km", [2, 5]),
    ],
)
def test_rank_matches_every_term_fuzzily(query: str, expected: list[int]) -> None:
    assert rank(TEXTS, query).ids == expected


def test_rank_without_terms_keeps_every_text_in_id_order() -> None:
    assert rank(TEXTS, "  ,; ").ids == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    ("query", "first"), [("sorpasso destra", 4), ("il sorpasso a destra", 4), ("fendi", 3)]
)
def test_rank_puts_the_closest_text_first(query: str, first: int) -> None:
    assert rank(TEXTS, query).ids[0] == first


def test_rank_prefers_exact_phrases() -> None:
    texts = {1: "curva e sorpasso", 2: "sorpasso in curva"}

    assert rank(texts, "sorpasso in curva").ids == [2, 1]


def test_rank_reports_the_matched_words() -> None:
    assert rank(TEXTS, "sorpaso").matched_words == {"sorpasso"}


def test_highlight_marks_matched_words_ignoring_case_and_accents() -> None:
    segments = highlight("Velocità e VELOCITA.", frozenset({"velocita"}))

    assert segments == [
        Segment(text="Velocità", matched=True),
        Segment(text=" e ", matched=False),
        Segment(text="VELOCITA", matched=True),
        Segment(text=".", matched=False),
    ]


def test_rank_treats_short_words_as_optional() -> None:
    assert rank(TEXTS, "il sorpasso in curva").ids == [1]
