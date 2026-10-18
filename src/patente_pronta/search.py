import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher

WORD = re.compile(r"\w+")
EXACT_SCORE = 1.0
PREFIX_SCORE = 0.9
INFIX_SCORE = 0.7
PHRASE_BONUS = 1.0
MIN_PARTIAL_LENGTH = 3
MIN_FUZZY_LENGTH = 4
MAX_LENGTH_GAP = 2
FUZZY_CUTOFF = 0.8
FUZZY_WEIGHT = 0.6


@dataclass(frozen=True, slots=True)
class Ranking:
    ids: list[int]
    matched_words: frozenset[str]


@dataclass(frozen=True, slots=True)
class Segment:
    text: str
    matched: bool


def rank(texts: Mapping[int, str], query: str) -> Ranking:
    terms = words(query)
    if not terms:
        return Ranking(ids=sorted(texts), matched_words=frozenset())
    required = [term for term in terms if _is_significant(term)] or terms
    normalized = {key: words(text) for key, text in texts.items()}
    vocabulary = {word for text_words in normalized.values() for word in text_words}
    term_matches = [_matches(term, vocabulary) for term in required]
    phrase = " ".join(terms)
    scores: dict[int, float] = {}
    for key, text_words in normalized.items():
        score = _score(set(text_words), term_matches)
        if score is not None:
            scores[key] = score + (PHRASE_BONUS if phrase in " ".join(text_words) else 0)
    return Ranking(
        ids=sorted(scores, key=lambda key: (-scores[key], key)),
        matched_words=frozenset(word for matches in term_matches for word in matches),
    )


def highlight(text: str, matched_words: frozenset[str]) -> list[Segment]:
    segments: list[Segment] = []
    start = 0
    for match in WORD.finditer(text):
        if _normalize(match.group()) not in matched_words:
            continue
        if match.start() > start:
            segments.append(Segment(text=text[start : match.start()], matched=False))
        segments.append(Segment(text=match.group(), matched=True))
        start = match.end()
    if start < len(text):
        segments.append(Segment(text=text[start:], matched=False))
    return segments


def words(text: str) -> list[str]:
    return WORD.findall(_normalize(text).replace("_", " "))


def _is_significant(term: str) -> bool:
    return term.isdigit() or len(term) >= MIN_PARTIAL_LENGTH


def _matches(term: str, vocabulary: Iterable[str]) -> dict[str, float]:
    matches: dict[str, float] = {}
    for word in vocabulary:
        score = _similarity(term, word)
        if score:
            matches[word] = score
    return matches


def _similarity(term: str, word: str) -> float:
    if term == word:
        return EXACT_SCORE
    if term.isdigit() or len(term) < MIN_PARTIAL_LENGTH:
        return 0
    if word.startswith(term):
        return PREFIX_SCORE
    if len(term) < MIN_FUZZY_LENGTH:
        return 0
    return _fuzzy_similarity(term, word)


def _fuzzy_similarity(term: str, word: str) -> float:
    if term in word:
        return INFIX_SCORE
    if abs(len(term) - len(word)) > MAX_LENGTH_GAP:
        return 0
    ratio = SequenceMatcher(None, term, word).ratio()
    return FUZZY_WEIGHT * ratio if ratio >= FUZZY_CUTOFF else 0


def _score(text_words: set[str], term_matches: list[dict[str, float]]) -> float | None:
    total = 0.0
    for matches in term_matches:
        best = max((matches[word] for word in text_words if word in matches), default=0.0)
        if not best:
            return None
        total += best
    return total


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
