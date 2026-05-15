from __future__ import annotations

import json
import mimetypes
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import database
from .config import ROOT
from .detector import health_payload
from .scanner import rescan_photo, scan_folder
from .tagging import tag_face


class LocalFaceHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(health_payload())
            return
        if parsed.path == "/api/files":
            with database.connection() as conn:
                self.send_json(database.list_files(conn))
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

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            self.handle_scan()
            return
        if parsed.path == "/api/tag":
            self.handle_tag()
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

    def handle_scan(self) -> None:
        payload = self.read_json()
        try:
            result = scan_folder(Path(payload.get("path", "")).expanduser())
            self.send_json({"ok": True, **result})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_tag(self) -> None:
        payload = self.read_json()
        result = tag_face(
            file_id=payload["fileId"],
            face_id=payload["faceId"],
            tag=payload.get("tag", ""),
        )
        status = result.pop("status", 200)
        self.send_json(result, status=status)

    def handle_ignore_face(self) -> None:
        payload = self.read_json()
        with database.connection() as conn:
            with conn:
                removed = database.ignore_face(conn, payload["fileId"], payload["faceId"])
            if not removed:
                self.send_json({"ok": False, "error": "Face not found"}, status=404)
                return
            self.send_json({"ok": True, "files": database.list_files(conn)})

    def handle_rescan_photo(self, reset_ignored: bool) -> None:
        payload = self.read_json()
        try:
            result = rescan_photo(payload["fileId"], reset_ignored=reset_ignored)
            self.send_json({"ok": True, **result})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_clear(self) -> None:
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


def single_param(params: dict, key: str) -> str | None:
    value = params.get(key, [""])[0].strip()
    return value or None
