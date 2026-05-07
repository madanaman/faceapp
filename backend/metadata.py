from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

TAGS = ExifTags.TAGS
GPS_TAGS = ExifTags.GPSTAGS


def extract_photo_metadata(path: Path) -> dict:
    empty = {
        "taken_at": None,
        "camera_make": None,
        "camera_model": None,
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "orientation": None,
        "exif_json": "{}",
    }

    try:
        with Image.open(path) as image:
            raw_exif = image.getexif()
            if not raw_exif:
                return empty

            exif = decode_exif(raw_exif)
            gps = decode_gps(raw_exif.get_ifd(ExifTags.IFD.GPSInfo)) if ExifTags.IFD.GPSInfo in raw_exif else {}
            latitude, longitude = gps_coordinates(gps)

            return {
                "taken_at": parse_taken_at(
                    exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized") or exif.get("DateTime")
                ),
                "camera_make": clean_text(exif.get("Make")),
                "camera_model": clean_text(exif.get("Model")),
                "latitude": latitude,
                "longitude": longitude,
                "altitude": rational_to_float(gps.get("GPSAltitude")),
                "orientation": int(exif["Orientation"]) if exif.get("Orientation") else None,
                "exif_json": json.dumps(serializable_exif(exif, gps)),
            }
    except Exception:
        return empty


def decode_exif(raw_exif) -> dict[str, Any]:
    return {TAGS.get(tag_id, tag_id): value for tag_id, value in raw_exif.items()}


def decode_gps(raw_gps) -> dict[str, Any]:
    return {GPS_TAGS.get(tag_id, tag_id): value for tag_id, value in raw_gps.items()}


def parse_taken_at(value) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue
    return text


def gps_coordinates(gps: dict[str, Any]) -> tuple[float | None, float | None]:
    latitude = gps_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
    longitude = gps_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    return latitude, longitude


def gps_decimal(value, ref) -> float | None:
    if not value or not ref:
        return None
    degrees, minutes, seconds = [rational_to_float(part) for part in value]
    if degrees is None or minutes is None or seconds is None:
        return None
    decimal = degrees + minutes / 60 + seconds / 3600
    if str(ref).upper() in {"S", "W"}:
        decimal *= -1
    return decimal


def rational_to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except TypeError:
        try:
            numerator, denominator = value
            return float(numerator) / float(denominator)
        except Exception:
            return None


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def serializable_exif(exif: dict[str, Any], gps: dict[str, Any]) -> dict:
    simple = {str(key): simple_value(value) for key, value in exif.items() if key != "GPSInfo"}
    simple["GPSInfo"] = {str(key): simple_value(value) for key, value in gps.items()}
    return simple


def simple_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [simple_value(item) for item in value]
    if isinstance(value, list):
        return [simple_value(item) for item in value]
    return str(value)
