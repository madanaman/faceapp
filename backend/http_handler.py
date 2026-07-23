from __future__ import annotations

import json
import logging
import mimetypes
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import database
from .config import STATIC_ROOT
from .detector import health_payload
from .scanner import rescan_photo, scan_folder
from .search_parser import parse_search_query
from .tagging import tag_face

logger = logging.getLogger(__name__)


class LocalFaceHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/ready":
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/health":
            self.send_json(health_payload())
            return
        if parsed.path == "/api/files":
            with database.connection() as conn:
                self.send_json(database.list_files(conn))
            return
        if parsed.path == "/api/albums":
            with database.connection() as conn:
                self.send_json(database.list_albums(conn))
            return
        if parsed.path == "/api/photo-tags":
            with database.connection() as conn:
                self.send_json(database.list_tags(conn))
            return
        if parsed.path == "/api/search/parse":
            params = parse_qs(parsed.query)
            with database.connection() as conn:
                self.send_json(parse_search_query(conn, single_param(params, "q") or ""))
            return
        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            with database.connection() as conn:
                try:
                    self.send_json(
                        database.search_files(
                            conn,
                            year=single_param(params, "year"),
                            city=single_param(params, "city"),
                            place=single_param(params, "place"),
                            album=single_param(params, "album"),
                            tag=single_param(params, "tag"),
                        )
                    )
                except ValueError as exc:
                    self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/media":
            params = parse_qs(parsed.query)
            self.send_media(Path(params.get("path", [""])[0]))
            return
        super().do_GET()

    def end_headers(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_header("access-control-allow-origin", "*")
            self.send_header("access-control-allow-methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("access-control-allow-headers", "content-type")
        if not parsed.path.startswith("/api/media"):
            self.send_header("cache-control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            self.handle_scan()
            return
        if parsed.path == "/api/pick-folder":
            self.handle_pick_folder()
            return
        if parsed.path == "/api/tag":
            self.handle_tag()
            return
        if parsed.path == "/api/albums":
            self.handle_create_album()
            return
        if parsed.path == "/api/albums/photos":
            self.handle_add_photo_to_album()
            return
        if parsed.path == "/api/photo-tags":
            self.handle_create_photo_tag()
            return
        if parsed.path == "/api/photos/tags":
            self.handle_add_photo_tag()
            return
        if parsed.path == "/api/ignore-face":
            self.handle_ignore_face()
            return
        if parsed.path == "/api/rescan-photo":
            self.handle_rescan_photo(reset_ignored=False)
            return
        if parsed.path == "/api/reset-ignored-faces":
            self.handle_rescan_photo(reset_ignored=True)
            return
        if parsed.path == "/api/clear":
            self.handle_clear()
            return
        self.send_error(404)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/albums/photos":
            self.handle_remove_photo_from_album()
            return
        if parsed.path == "/api/photos/tags":
            self.handle_remove_photo_tag()
            return
        self.send_error(404)

    def handle_scan(self) -> None:
        payload = self.read_json()
        logger.info(
            "Scan request path=%s mode=%s album=%s",
            payload.get("path", ""),
            payload.get("scanMode", "photos"),
            payload.get("albumName", ""),
        )
        try:
            result = scan_folder(
                Path(payload.get("path", "")).expanduser(),
                scan_mode=payload.get("scanMode", "photos"),
                album_name=payload.get("albumName", ""),
            )
            logger.info(
                "Scan completed files=%s auto_tagged=%s warnings=%s",
                len(result.get("files", [])),
                result.get("autoTagged", 0),
                len(result.get("warnings", [])),
            )
            self.send_json({"ok": True, **result})
        except Exception as exc:
            logger.exception("Scan failed")
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_pick_folder(self) -> None:
        if sys.platform != "darwin":
            self.send_json({"ok": False, "error": "Folder picker is only wired for macOS desktop builds."}, status=501)
            return
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'POSIX path of (choose folder with prompt "Choose a folder to scan")',
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)
            return
        if result.returncode != 0:
            self.send_json({"ok": True, "path": ""})
            return
        self.send_json({"ok": True, "path": result.stdout.strip("\n")})

    def handle_tag(self) -> None:
        payload = self.read_json()
        logger.info("Tag request file_id=%s face_id=%s tag=%s", payload.get("fileId"), payload.get("faceId"), payload.get("tag", ""))
        result = tag_face(
            file_id=payload["fileId"],
            face_id=payload["faceId"],
            tag=payload.get("tag", ""),
        )
        status = result.pop("status", 200)
        self.send_json(result, status=status)

    def handle_create_album(self) -> None:
        payload = self.read_json()
        self.run_mutation(lambda conn: database.create_album(conn, payload.get("name", ""), payload.get("description", "")))

    def handle_add_photo_to_album(self) -> None:
        payload = self.read_json()
        self.run_mutation(lambda conn: database.add_photo_to_album(conn, int(payload["albumId"]), payload["fileId"]))

    def handle_remove_photo_from_album(self) -> None:
        payload = self.read_json()
        self.run_mutation(lambda conn: database.remove_photo_from_album(conn, int(payload["albumId"]), payload["fileId"]))

    def handle_create_photo_tag(self) -> None:
        payload = self.read_json()
        self.run_mutation(lambda conn: database.create_photo_tag(conn, payload.get("name", ""), payload.get("kind", "custom")))

    def handle_add_photo_tag(self) -> None:
        payload = self.read_json()
        self.run_mutation(lambda conn: database.add_photo_tag(conn, payload["fileId"], payload.get("tag", "")))

    def handle_remove_photo_tag(self) -> None:
        payload = self.read_json()
        self.run_mutation(lambda conn: database.remove_photo_tag(conn, payload["fileId"], int(payload["tagId"])))

    def run_mutation(self, mutation) -> None:
        try:
            with database.connection() as conn:
                with conn:
                    mutation(conn)
                self.send_json(
                    {
                        "ok": True,
                        "files": database.list_files(conn),
                        "albums": database.list_albums(conn),
                        "tags": database.list_tags(conn),
                    }
                )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Mutation failed: %s", exc)
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_ignore_face(self) -> None:
        payload = self.read_json()
        logger.info("Ignore face request file_id=%s face_id=%s", payload.get("fileId"), payload.get("faceId"))
        with database.connection() as conn:
            with conn:
                removed = database.ignore_face(conn, payload["fileId"], payload["faceId"])
            if not removed:
                self.send_json({"ok": False, "error": "Face not found"}, status=404)
                return
            self.send_json({"ok": True, "files": database.list_files(conn)})

    def handle_rescan_photo(self, reset_ignored: bool) -> None:
        payload = self.read_json()
        logger.info("Rescan request file_id=%s reset_ignored=%s", payload.get("fileId"), reset_ignored)
        try:
            result = rescan_photo(payload["fileId"], reset_ignored=reset_ignored)
            logger.info(
                "Rescan completed file_id=%s auto_tagged=%s warnings=%s",
                payload.get("fileId"),
                result.get("autoTagged", 0),
                len(result.get("warnings", [])),
            )
            self.send_json({"ok": True, **result})
        except Exception as exc:
            logger.exception("Rescan failed")
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_clear(self) -> None:
        logger.warning("Clear index request received")
        with database.connection() as conn:
            with conn:
                database.clear_files(conn)
            self.send_json({"ok": True})

    def read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_media(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format % args)


def single_param(params: dict, key: str) -> str | None:
    value = params.get(key, [""])[0].strip()
    return value or None
