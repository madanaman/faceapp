#!/usr/bin/env python3
from __future__ import annotations

from http.server import ThreadingHTTPServer

from backend.http_handler import LocalFaceHandler


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), LocalFaceHandler)
    print("Serving Local Face Photos at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
