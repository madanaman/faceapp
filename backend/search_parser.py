from __future__ import annotations

from datetime import date
import logging
import re
from typing import Iterable

from . import database

logger = logging.getLogger(__name__)

FILLER_WORDS = {
    "a",
    "all",
    "and",
    "by",
    "for",
    "find",
    "from",
    "give",
    "i",
    "in",
    "library",
    "me",
    "my",
    "of",
    "on",
    "please",
    "search",
    "show",
    "taken",
    "the",
    "to",
    "with",
}
PHOTO_WORDS = {"image", "images", "photo", "photos", "pic", "pics", "picture", "pictures"}
VIDEO_WORDS = {"clip", "clips", "movie", "movies", "video", "videos"}
MONTHS = {
    "jan": "01",
    "january": "01",
    "feb": "02",
    "february": "02",
    "mar": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "may": "05",
    "jun": "06",
    "june": "06",
    "jul": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dec": "12",
    "december": "12",
}


def parse_search_query(conn, query: str, today: date | None = None) -> dict:
    people = database.list_people(conn)
    albums = database.list_albums(conn)
    tags = database.list_tags(conn)
    return parse_query(query, people=people, albums=albums, tags=tags, today=today)


def parse_query(
    query: str,
    people: Iterable[dict],
    albums: Iterable[dict],
    tags: Iterable[dict],
    today: date | None = None,
) -> dict:
    today = today or date.today()
    raw_query = query.strip()
    normalized = normalize_text(raw_query)
    tokens = normalized.split()
    recognized_positions: set[int] = set()

    entities, entity_positions = match_entities(tokens, people=people, albums=albums, tags=tags)
    recognized_positions.update(entity_positions)

    date_parts, date_positions = parse_dates(raw_query, tokens, today=today)
    recognized_positions.update(date_positions)

    media_type, media_positions = parse_media_type(tokens)
    recognized_positions.update(media_positions)

    ignored_words = sorted({token for token in tokens if token in FILLER_WORDS})
    recognized_positions.update(index for index, token in enumerate(tokens) if token in FILLER_WORDS)
    unused_words = [
        token
        for index, token in enumerate(tokens)
        if index not in recognized_positions and token not in FILLER_WORDS
    ]
    terms = unique_preserving_order(entity["name"] for entity in entities)

    result = {
        "query": raw_query,
        "terms": terms,
        "entities": entities,
        "mediaType": media_type,
        "year": date_parts["year"],
        "month": date_parts["month"],
        "date": date_parts["date"],
        "ignoredWords": ignored_words,
        "unusedWords": unused_words,
        "hasInterpretation": bool(terms or media_type or any(date_parts.values())),
    }
    logger.debug("Parsed search query=%r result=%s", raw_query, result)
    return result


def match_entities(tokens: list[str], people: Iterable[dict], albums: Iterable[dict], tags: Iterable[dict]) -> tuple[list[dict], set[int]]:
    candidates = []
    for kind, rows in (("person", people), ("album", albums), ("tag", tags)):
        for row in rows:
            name = (row.get("name") or "").strip()
            phrase_tokens = normalize_text(name).split()
            if not phrase_tokens:
                continue
            candidates.append((kind, name, phrase_tokens))

    candidates.sort(key=lambda candidate: (-len(candidate[2]), candidate[1].casefold()))
    occupied: set[int] = set()
    entities = []
    seen_names: set[str] = set()

    for kind, name, phrase_tokens in candidates:
        span = find_phrase_span(tokens, phrase_tokens, occupied)
        if not span:
            continue
        normalized_name = normalize_text(name)
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        occupied.update(span)
        entities.append({"type": kind, "name": name})

    entities.sort(key=lambda entity: first_phrase_index(tokens, normalize_text(entity["name"]).split()))
    return entities, occupied


def find_phrase_span(tokens: list[str], phrase_tokens: list[str], occupied: set[int]) -> set[int]:
    phrase_length = len(phrase_tokens)
    for start in range(0, len(tokens) - phrase_length + 1):
        span = set(range(start, start + phrase_length))
        if span & occupied:
            continue
        if tokens[start : start + phrase_length] == phrase_tokens:
            return span
    return set()


def first_phrase_index(tokens: list[str], phrase_tokens: list[str]) -> int:
    phrase_length = len(phrase_tokens)
    for start in range(0, len(tokens) - phrase_length + 1):
        if tokens[start : start + phrase_length] == phrase_tokens:
            return start
    return len(tokens)


def parse_media_type(tokens: list[str]) -> tuple[str, set[int]]:
    photo_positions = {index for index, token in enumerate(tokens) if token in PHOTO_WORDS}
    video_positions = {index for index, token in enumerate(tokens) if token in VIDEO_WORDS}
    if photo_positions and video_positions:
        return "both", photo_positions | video_positions
    if photo_positions:
        return "photos", photo_positions
    if video_positions:
        return "videos", video_positions
    return "", set()


def parse_dates(raw_query: str, tokens: list[str], today: date) -> tuple[dict[str, str], set[int]]:
    result = {"year": "", "month": "", "date": ""}
    positions: set[int] = set()
    date_match = re.search(r"\b((?:19|20)\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b", raw_query)
    if date_match:
        year, month, day = date_match.groups()
        result["date"] = f"{year}-{int(month):02d}-{int(day):02d}"
        result["year"] = year
        result["month"] = f"{int(month):02d}"

    if not result["year"]:
        if "this" in tokens and "year" in tokens:
            result["year"] = str(today.year)
        elif "last" in tokens and "year" in tokens:
            result["year"] = str(today.year - 1)
        else:
            year = next((token for token in tokens if re.fullmatch(r"(?:19|20)\d{2}", token)), "")
            result["year"] = year

    if not result["month"]:
        month = next((MONTHS[token] for token in tokens if token in MONTHS), "")
        result["month"] = month

    for index, token in enumerate(tokens):
        if token == result["year"] or token in MONTHS or token in {"this", "last", "year"}:
            positions.add(index)
    return result, positions


def normalize_text(value: str) -> str:
    normalized = value.casefold().replace("’", "'")
    normalized = re.sub(r"\b([a-z0-9]+)'s\b", r"\1", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        key = normalize_text(value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique
