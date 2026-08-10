from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from . import database
from .config import APP_DATA_DIR, DB_PATH, RESTORED_MEDIA_DIR, THUMBNAIL_DIR

BACKUP_FORMAT = "local-face-photos-backup"
BACKUP_FORMAT_VERSION = 1
APP_VERSION = "0.1.0"
MANIFEST_NAME = "manifest.json"
DATABASE_BACKUP_NAME = "face_index.sqlite3"
THUMBNAILS_BACKUP_DIR = "thumbnails"
MEDIA_BACKUP_DIR = Path("media") / "by-id"
MEDIA_INDEX_NAME = "media-index.jsonl"
logger = logging.getLogger(__name__)


def create_backup(
    target: Path,
    include_media: bool = False,
    db_path: Path = DB_PATH,
    thumbnail_dir: Path = THUMBNAIL_DIR,
) -> dict:
    backup_root = target.expanduser()
    backup_root.mkdir(parents=True, exist_ok=True)
    db_path = db_path.expanduser()
    thumbnail_dir = thumbnail_dir.expanduser()
    if not db_path.exists():
        raise ValueError("Database file does not exist.")

    logger.info("Creating backup target=%s include_media=%s", backup_root, include_media)
    backup_db_path = backup_root / DATABASE_BACKUP_NAME
    copy_sqlite_database(db_path, backup_db_path)
    thumbnail_stats = copy_thumbnails(thumbnail_dir, backup_root / THUMBNAILS_BACKUP_DIR)

    media_index: dict | None = None
    warnings: list[str] = []
    photo_rows = indexed_photos(backup_db_path)
    if include_media:
        media_root = backup_root / MEDIA_BACKUP_DIR
        media_root.mkdir(parents=True, exist_ok=True)
        media_index, warnings = write_media_index(photo_rows, media_root, backup_root / MEDIA_INDEX_NAME)

    manifest = {
        "format": BACKUP_FORMAT,
        "formatVersion": BACKUP_FORMAT_VERSION,
        "appVersion": APP_VERSION,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": "full" if include_media else "metadata",
        "database": {
            "path": DATABASE_BACKUP_NAME,
            "sha256": sha256_file(backup_db_path),
            "size": backup_db_path.stat().st_size,
        },
        "thumbnails": thumbnail_stats,
        "counts": backup_counts(backup_db_path, media_index),
        "warnings": warnings,
    }
    if media_index:
        manifest["mediaIndex"] = media_index
    write_json(backup_root / MANIFEST_NAME, manifest)
    logger.info("Backup created target=%s mode=%s photos=%s warnings=%s", backup_root, manifest["mode"], len(photo_rows), len(warnings))
    return {
        "path": str(backup_root),
        "manifest": manifest,
        "warnings": warnings,
    }


def validate_restore_source(source: Path, verify_media: bool = True) -> dict:
    backup_root = source.expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    manifest = read_manifest(backup_root, errors)
    if not manifest:
        return {"valid": False, "errors": errors, "warnings": warnings}

    if manifest.get("format") != BACKUP_FORMAT:
        errors.append("Unsupported backup format.")
    if manifest.get("formatVersion") != BACKUP_FORMAT_VERSION:
        errors.append("Unsupported backup version.")

    database_info = manifest.get("database") or {}
    backup_db_path = backup_root / database_info.get("path", DATABASE_BACKUP_NAME)
    if not backup_db_path.exists():
        errors.append("Backup database file is missing.")
    elif database_info.get("sha256") and sha256_file(backup_db_path) != database_info.get("sha256"):
        errors.append("Backup database checksum does not match manifest.")

    thumbnails = manifest.get("thumbnails") or {}
    if thumbnails.get("count", 0) and not (backup_root / thumbnails.get("path", THUMBNAILS_BACKUP_DIR)).exists():
        errors.append("Backup thumbnails folder is missing.")

    if verify_media and manifest.get("mode") == "full":
        for entry in media_entries(backup_root, manifest, errors):
            if entry.get("missing"):
                warnings.append(f"Original media was missing during backup: {entry.get('originalPath', '')}")
                continue
            backup_path = backup_root / entry.get("backupPath", "")
            if not backup_path.exists():
                warnings.append(f"Backed-up media file is missing: {entry.get('backupPath', '')}")
                continue
            if entry.get("sha256") and sha256_file(backup_path) != entry.get("sha256"):
                warnings.append(f"Backed-up media checksum mismatch: {entry.get('backupPath', '')}")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "mode": manifest.get("mode", ""),
        "manifest": manifest,
    }


def restore_backup(
    source: Path,
    db_path: Path = DB_PATH,
    thumbnail_dir: Path = THUMBNAIL_DIR,
    restored_media_dir: Path = RESTORED_MEDIA_DIR,
    app_data_dir: Path = APP_DATA_DIR,
) -> dict:
    backup_root = source.expanduser()
    validation = validate_restore_source(backup_root)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]) or "Backup is invalid.")

    manifest = validation["manifest"]
    db_path = db_path.expanduser()
    thumbnail_dir = thumbnail_dir.expanduser()
    restored_media_dir = restored_media_dir.expanduser()
    app_data_dir = app_data_dir.expanduser()
    app_data_dir.mkdir(parents=True, exist_ok=True)

    safety_db = create_safety_database_copy(db_path, app_data_dir)
    source_db = backup_root / manifest["database"]["path"]
    copy_restored_database(source_db, db_path)
    restore_thumbnails(backup_root / manifest.get("thumbnails", {}).get("path", THUMBNAILS_BACKUP_DIR), thumbnail_dir)

    restored_media_count = 0
    skipped_media_count = 0
    if manifest.get("mode") == "full":
        media_restore = restore_media_files(backup_root, manifest, db_path, restored_media_dir)
        restored_media_count = media_restore["restored"]
        skipped_media_count = media_restore["skipped"]
        for warning in media_restore["warnings"]:
            if warning not in validation["warnings"]:
                validation["warnings"].append(warning)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        database.ensure_schema(conn)
        database.run_migrations(conn)
        files = database.list_files(conn)
    finally:
        conn.close()

    logger.info("Backup restored source=%s mode=%s files=%s", backup_root, manifest.get("mode"), len(files))
    return {
        "validation": validation,
        "mode": manifest.get("mode", ""),
        "safetyBackupPath": str(safety_db) if safety_db else "",
        "restoredMediaCount": restored_media_count,
        "skippedMediaCount": skipped_media_count,
        "files": files,
    }


def copy_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.execute("pragma wal_checkpoint(full)")
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()


def copy_restored_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        stale = Path(f"{target}{suffix}")
        if stale.exists():
            stale.unlink()
    shutil.copy2(source, target)


def create_safety_database_copy(db_path: Path, app_data_dir: Path) -> Path | None:
    if not db_path.exists():
        return None
    safety_dir = app_data_dir / "restore-safety"
    safety_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safety_path = safety_dir / f"face_index.before-restore-{timestamp}.sqlite3"
    copy_sqlite_database(db_path, safety_path)
    return safety_path


def copy_thumbnails(source: Path, target: Path) -> dict:
    if target.exists():
        shutil.rmtree(target)
    if not source.exists():
        target.mkdir(parents=True, exist_ok=True)
        return {"path": THUMBNAILS_BACKUP_DIR, "count": 0, "size": 0}
    shutil.copytree(source, target)
    count, size = directory_stats(target)
    return {"path": THUMBNAILS_BACKUP_DIR, "count": count, "size": size}


def restore_thumbnails(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    if source.exists():
        shutil.copytree(source, target)
    else:
        target.mkdir(parents=True, exist_ok=True)


def restore_media_files(backup_root: Path, manifest: dict, db_path: Path, restored_media_dir: Path) -> dict:
    backup_id = backup_identifier(manifest, backup_root)
    target_root = restored_media_dir / backup_id / MEDIA_BACKUP_DIR
    target_root.mkdir(parents=True, exist_ok=True)
    path_updates: list[tuple[str, str]] = []
    skipped = 0
    warnings: list[str] = []

    index_errors: list[str] = []
    for entry in media_entries(backup_root, manifest, index_errors):
        if index_errors:
            break
        if entry.get("missing") or not entry.get("backupPath"):
            skipped += 1
            continue
        source_path = backup_root / entry["backupPath"]
        if not source_path.exists():
            skipped += 1
            warnings.append(f"Backed-up media file is missing: {entry.get('backupPath', '')}")
            continue
        if entry.get("sha256") and sha256_file(source_path) != entry.get("sha256"):
            skipped += 1
            warnings.append(f"Backed-up media checksum mismatch: {entry.get('backupPath', '')}")
            continue
        target_path = target_root / Path(entry["backupPath"]).name
        shutil.copy2(source_path, target_path)
        path_updates.append((str(target_path), entry["photoId"]))

    if path_updates:
        conn = sqlite3.connect(db_path)
        try:
            conn.executemany("update photos set path = ? where id = ?", path_updates)
            conn.commit()
        finally:
            conn.close()
    warnings.extend(index_errors)
    return {"restored": len(path_updates), "skipped": skipped, "warnings": warnings}


def indexed_photos(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute("select id, path, name, type, signature from photos order by name").fetchall()
    finally:
        conn.close()


def backup_counts(db_path: Path, media_index: dict | None) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        return {
            "photos": conn.execute("select count(*) from photos").fetchone()[0],
            "faces": conn.execute("select count(*) from faces").fetchone()[0],
            "albums": conn.execute("select count(*) from albums").fetchone()[0],
            "photoTags": conn.execute("select count(*) from photo_tags").fetchone()[0],
            "locations": conn.execute("select count(*) from photo_places").fetchone()[0],
            "mediaCopied": media_index.get("copied", 0) if media_index else 0,
            "mediaMissing": media_index.get("missing", 0) if media_index else 0,
        }
    finally:
        conn.close()


def write_media_index(photo_rows: list[sqlite3.Row], media_root: Path, index_path: Path) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    count = 0
    copied = 0
    missing = 0
    with index_path.open("w", encoding="utf-8") as handle:
        for row in photo_rows:
            entry, warning = copy_media_entry(row, media_root)
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
            count += 1
            if entry.get("missing"):
                missing += 1
            else:
                copied += 1
            if warning:
                warnings.append(warning)
    return (
        {
            "path": MEDIA_INDEX_NAME,
            "count": count,
            "copied": copied,
            "missing": missing,
            "size": index_path.stat().st_size,
            "sha256": sha256_file(index_path),
        },
        warnings,
    )


def media_entries(backup_root: Path, manifest: dict, errors: list[str] | None = None) -> list[dict]:
    if manifest.get("media") is not None:
        return manifest.get("media") or []

    media_index = manifest.get("mediaIndex") or {}
    index_path = backup_root / media_index.get("path", MEDIA_INDEX_NAME)
    if not index_path.exists():
        if errors is not None:
            errors.append("Backup media index file is missing.")
        return []
    if media_index.get("sha256") and sha256_file(index_path) != media_index.get("sha256"):
        if errors is not None:
            errors.append("Backup media index checksum does not match manifest.")
        return []

    entries: list[dict] = []
    with index_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                if errors is not None:
                    errors.append(f"Backup media index has invalid JSON on line {line_number}.")
                return []
    return entries


def copy_media_entry(row: sqlite3.Row, media_root: Path) -> tuple[dict, str]:
    original_path = Path(row["path"])
    entry = {
        "photoId": row["id"],
        "originalPath": row["path"],
        "originalName": row["name"],
        "signature": row["signature"],
        "type": row["type"],
    }
    if not original_path.exists() or not original_path.is_file():
        entry.update({"missing": True})
        return entry, f"Media file missing and was not copied: {row['path']}"

    filename = backup_media_filename(row["id"], original_path)
    target_path = media_root / filename
    shutil.copy2(original_path, target_path)
    entry.update(
        {
            "backupPath": str(MEDIA_BACKUP_DIR / filename),
            "size": target_path.stat().st_size,
            "sha256": sha256_file(target_path),
        }
    )
    return entry, ""


def backup_media_filename(photo_id: str, original_path: Path) -> str:
    digest = hashlib.sha1(photo_id.encode("utf-8")).hexdigest()[:24]
    suffix = original_path.suffix.lower()
    return f"{digest}{suffix}"


def backup_identifier(manifest: dict, backup_root: Path) -> str:
    created = (manifest.get("createdAt") or "").replace(":", "").replace("-", "").replace("+", "z")
    digest = hashlib.sha1(str(backup_root).encode("utf-8")).hexdigest()[:8]
    return f"{created or 'backup'}-{digest}"


def directory_stats(path: Path) -> tuple[int, int]:
    count = 0
    size = 0
    for current in path.rglob("*"):
        if current.is_file():
            count += 1
            size += current.stat().st_size
    return count, size


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(backup_root: Path, errors: list[str]) -> dict:
    manifest_path = backup_root / MANIFEST_NAME
    if not manifest_path.exists():
        errors.append("Backup manifest is missing.")
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append("Backup manifest is not valid JSON.")
        return {}
