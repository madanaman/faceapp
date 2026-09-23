from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
import hashlib
import json
import logging

from . import database

MIN_MEMORY_ITEMS = 2
MAX_MEMORIES = 24
logger = logging.getLogger(__name__)


def generate_local_memories(conn, today: date | None = None, limit: int = MAX_MEMORIES) -> list[dict]:
    """Generate lightweight local memories from indexed metadata only."""
    today = today or datetime.now(UTC).date()
    files = [record for record in database.list_files(conn) if photo_date(record)]
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    candidates: list[dict] = []

    on_this_day = build_on_this_day_memory(files, today)
    if on_this_day:
        candidates.append(on_this_day)
    candidates.extend(build_people_over_time_memories(files))
    candidates.extend(build_album_memories(files))
    candidates.extend(build_tag_memories(files))
    candidates.extend(build_place_memories(files))

    selected = sorted(candidates, key=lambda memory: (-memory["score"], memory["title"].lower()))[:limit]
    for memory in selected:
        memory["generatedAt"] = generated_at

    logger.info("Generated local memories candidates=%s selected=%s", len(candidates), len(selected))
    return database.save_generated_memories(conn, selected)


def build_on_this_day_memory(files: list[dict], today: date) -> dict | None:
    matches = [
        record for record in files
        if (taken := photo_date(record)) and taken.month == today.month and taken.day == today.day and taken.year < today.year
    ]
    if len(matches) < MIN_MEMORY_ITEMS:
        return None
    sorted_matches = sorted_by_date(matches, reverse=True)
    years = sorted({photo_date(record).year for record in sorted_matches})
    month_day = f"{today.strftime('%B')} {today.day}"
    return memory_record(
        memory_id=f"on-this-day-{today:%m-%d}",
        memory_type="on_this_day",
        title=f"On this day: {month_day}",
        subtitle=year_span_subtitle(years, len(sorted_matches)),
        records=sorted_matches,
        reason="Same calendar day",
        memory_date=today.isoformat(),
        score=100 + len(sorted_matches),
    )


def build_people_over_time_memories(files: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    display_names: dict[str, str] = {}
    for record in files:
        names = {face.get("tag", "").strip() for face in record.get("faces", []) if face.get("tag", "").strip()}
        for name in names:
            key = name.lower()
            display_names.setdefault(key, name)
            grouped[key].append(record)

    memories = []
    for key, records in grouped.items():
        years = sorted({photo_date(record).year for record in records if photo_date(record)})
        if len(records) < MIN_MEMORY_ITEMS or len(years) < 2:
            continue
        name = display_names[key]
        memories.append(
            memory_record(
                memory_id=stable_id("person-years", name),
                memory_type="people_over_time",
                title=f"{name} over the years",
                subtitle=year_span_subtitle(years, len(records)),
                records=sorted_by_date(records),
                reason=f"Tagged as {name}",
                score=80 + len(years) * 5 + len(records),
            )
        )
    return memories


def build_album_memories(files: list[dict]) -> list[dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    names: dict[int, str] = {}
    for record in files:
        for album in record.get("albums", []):
            names[album["id"]] = album["name"]
            grouped[album["id"]].append(record)
    return [
        memory_record(
            memory_id=stable_id("album", album_id),
            memory_type="album",
            title=names[album_id],
            subtitle=f"{len(records)} files in this album",
            records=sorted_by_date(records, reverse=True),
            reason=f"Album: {names[album_id]}",
            score=60 + len(records),
        )
        for album_id, records in grouped.items()
        if len(records) >= MIN_MEMORY_ITEMS
    ]


def build_tag_memories(files: list[dict]) -> list[dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    names: dict[int, str] = {}
    for record in files:
        for tag in record.get("tags", []):
            names[tag["id"]] = tag["name"]
            grouped[tag["id"]].append(record)
    return [
        memory_record(
            memory_id=stable_id("tag", tag_id),
            memory_type="photo_tag",
            title=names[tag_id],
            subtitle=f"{len(records)} files with this tag",
            records=sorted_by_date(records, reverse=True),
            reason=f"Photo tag: {names[tag_id]}",
            score=55 + len(records),
        )
        for tag_id, records in grouped.items()
        if len(records) >= MIN_MEMORY_ITEMS
    ]


def build_place_memories(files: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    labels: dict[str, str] = {}
    for record in files:
        place = record.get("place") or {}
        label = database.location_label(place.get("city") or "", place.get("region") or "", place.get("country") or "")
        if not label:
            continue
        key = label.lower()
        labels.setdefault(key, label)
        grouped[key].append(record)
    return [
        memory_record(
            memory_id=stable_id("place", label),
            memory_type="place",
            title=label,
            subtitle=f"{len(records)} files from this place",
            records=sorted_by_date(records, reverse=True),
            reason=f"Place: {label}",
            score=50 + len(records),
        )
        for key, records in grouped.items()
        for label in [labels[key]]
        if len(records) >= MIN_MEMORY_ITEMS
    ]


def memory_record(
    memory_id: str,
    memory_type: str,
    title: str,
    subtitle: str,
    records: list[dict],
    reason: str,
    score: float,
    memory_date: str = "",
) -> dict:
    photo_ids = [record["id"] for record in records]
    return {
        "id": memory_id,
        "type": memory_type,
        "title": title,
        "subtitle": subtitle,
        "coverPhotoId": photo_ids[0],
        "memoryDate": memory_date,
        "score": score,
        "photoIds": photo_ids,
        "reasons": {photo_id: reason for photo_id in photo_ids},
    }


def sorted_by_date(records: list[dict], reverse: bool = False) -> list[dict]:
    return sorted(records, key=lambda record: (photo_date(record), record["name"]), reverse=reverse)


def photo_date(record: dict) -> date | None:
    taken_at = (record.get("metadata") or {}).get("taken_at") or ""
    if not taken_at:
        return None
    try:
        return date.fromisoformat(taken_at[:10])
    except ValueError:
        return None


def year_span_subtitle(years: list[int], count: int) -> str:
    if not years:
        return f"{count} files"
    year_text = str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}"
    return f"{count} files from {year_text}"


def stable_id(prefix: str, *parts) -> str:
    digest = hashlib.sha1(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"

