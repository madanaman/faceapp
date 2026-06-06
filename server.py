#!/usr/bin/env python3
from __future__ import annotations

import logging
from http.server import ThreadingHTTPServer

from backend.logging_config import configure_logging

configure_logging()

from backend.http_handler import LocalFaceHandler

logger = logging.getLogger(__name__)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), LocalFaceHandler)
    logger.info("Serving Local Face Photos at http://127.0.0.1:8000")
    print("Serving Local Face Photos at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
