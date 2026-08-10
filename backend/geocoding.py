from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import database
from .config import (
    location_geocoder_throttle_seconds,
    location_nominatim_search_url,
    location_nominatim_url,
    location_nominatim_user_agent,
    location_resolve_limit,
    location_reverse_geocoder,
    location_reverse_geocoding_enabled,
    location_suggest_limit,
)

logger = logging.getLogger(__name__)


def suggest_locations(conn, query: str, limit: int | None = None) -> list[dict]:
    clean_query = query.strip()
    if not clean_query:
        return []

    max_results = limit or location_suggest_limit()
    suggestions = database.known_location_suggestions(conn, clean_query, max_results)
    if len(suggestions) >= max_results or not location_reverse_geocoding_enabled():
        return suggestions[:max_results]

    provider = location_reverse_geocoder()
    if provider != "nominatim":
        return suggestions[:max_results]

    try:
        suggestions.extend(search_nominatim(clean_query, max_results - len(suggestions)))
    except Exception as exc:
        logger.warning("Location suggestion lookup failed query=%s error=%s", clean_query, exc)

    return dedupe_suggestions(suggestions)[:max_results]


def location_from_payload(conn, payload: dict) -> dict:
    location = payload.get("location") if "location" in payload else payload
    location = location or {}
    city = (location.get("city") or "").strip()
    region = (location.get("region") or "").strip()
    country = (location.get("country") or "").strip()
    label = (location.get("label") or location.get("query") or "").strip()
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if any((city, region, country)):
        return {
            "city": city,
            "region": region,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
        }
    if label:
        suggestion = next(iter(suggest_locations(conn, label, limit=1)), None)
        if suggestion:
            return {
                "city": suggestion.get("city") or "",
                "region": suggestion.get("region") or "",
                "country": suggestion.get("country") or "",
                "latitude": suggestion.get("latitude"),
                "longitude": suggestion.get("longitude"),
            }
        return {"city": label, "region": "", "country": "", "latitude": latitude, "longitude": longitude}
    return {}


def resolve_missing_photo_locations(conn, limit: int | None = None) -> dict:
    if not location_reverse_geocoding_enabled():
        return {"resolved": 0, "cached": 0, "skipped": 0, "error": "Online location resolution is disabled."}

    provider = location_reverse_geocoder()
    if provider != "nominatim":
        return {"resolved": 0, "cached": 0, "skipped": 0, "error": f"Unsupported location provider: {provider}"}

    resolved = 0
    cached = 0
    skipped = 0
    last_lookup_at = 0.0
    rows = database.unresolved_gps_places(conn, limit or location_resolve_limit())
    logger.info("Resolving GPS locations rows=%s provider=%s", len(rows), provider)

    for row in rows:
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        if latitude is None or longitude is None:
            skipped += 1
            continue

        cached_place = database.cached_location(conn, latitude, longitude)
        if cached_place:
            database.save_place(conn, row["photo_id"], cache_to_place(cached_place))
            cached += 1
            continue

        wait_seconds = location_geocoder_throttle_seconds() - (time.monotonic() - last_lookup_at)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

        try:
            place = reverse_geocode_nominatim(latitude, longitude)
            last_lookup_at = time.monotonic()
        except Exception as exc:
            skipped += 1
            logger.warning("Reverse geocode failed photo_id=%s error=%s", row["photo_id"], exc)
            continue

        if not any(place.get(key) for key in ("city", "region", "country")):
            skipped += 1
            continue

        database.save_location_cache(conn, latitude, longitude, place, provider)
        database.save_place(
            conn,
            row["photo_id"],
            {
                **place,
                "latitude": latitude,
                "longitude": longitude,
                "source": "gps_reverse_geocode",
            },
        )
        resolved += 1

    logger.info("Location resolution complete resolved=%s cached=%s skipped=%s", resolved, cached, skipped)
    return {"resolved": resolved, "cached": cached, "skipped": skipped}


def cache_to_place(row: dict) -> dict:
    return {
        "city": row.get("city"),
        "region": row.get("region"),
        "country": row.get("country"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "source": "gps_reverse_geocode",
    }


def reverse_geocode_nominatim(latitude: float, longitude: float) -> dict:
    query = urlencode(
        {
            "format": "jsonv2",
            "lat": latitude,
            "lon": longitude,
            "zoom": 10,
            "addressdetails": 1,
        }
    )
    request = Request(
        f"{location_nominatim_url()}?{query}",
        headers={"User-Agent": location_nominatim_user_agent()},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_nominatim_place(payload)


def search_nominatim(query: str, limit: int) -> list[dict]:
    if limit <= 0:
        return []
    request_query = urlencode(
        {
            "format": "jsonv2",
            "q": query,
            "limit": limit,
            "addressdetails": 1,
        }
    )
    request = Request(
        f"{location_nominatim_search_url()}?{request_query}",
        headers={"User-Agent": location_nominatim_user_agent()},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    suggestions = [parse_nominatim_suggestion(item) for item in payload]
    return [suggestion for suggestion in suggestions if suggestion.get("label")]


def parse_nominatim_place(payload: dict) -> dict:
    address = payload.get("address") or {}
    city = first_present(
        address,
        "city",
        "town",
        "village",
        "municipality",
        "hamlet",
        "county",
    )
    region = first_present(address, "state", "province", "region", "state_district")
    return {
        "city": city,
        "region": region,
        "country": address.get("country") or "",
    }


def parse_nominatim_suggestion(payload: dict) -> dict:
    place = parse_nominatim_place(payload)
    latitude = payload.get("lat")
    longitude = payload.get("lon")
    suggestion = {
        **place,
        "latitude": float(latitude) if latitude not in (None, "") else None,
        "longitude": float(longitude) if longitude not in (None, "") else None,
        "provider": "nominatim",
        "source": "online_search",
    }
    suggestion["label"] = database.location_label(suggestion["city"], suggestion["region"], suggestion["country"])
    if not suggestion["label"]:
        suggestion["label"] = payload.get("display_name") or ""
    return suggestion


def dedupe_suggestions(suggestions: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for suggestion in suggestions:
        key = database.location_suggestion_key(suggestion)
        if key in seen:
            continue
        seen.add(key)
        result.append(suggestion)
    return result


def first_present(values: dict, *keys: str) -> str:
    for key in keys:
        value = values.get(key)
        if value:
            return value
    return ""
