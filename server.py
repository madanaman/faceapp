#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from http.server import ThreadingHTTPServer

from backend.logging_config import configure_logging

configure_logging()

from backend.http_handler import LocalFaceHandler

logger = logging.getLogger(__name__)


def main() -> None:
    host = os.environ.get("LOCAL_FACE_HOST", "127.0.0.1")
    port = int(os.environ.get("LOCAL_FACE_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), LocalFaceHandler)
    logger.info("Serving Local Face Photos at http://%s:%s", host, port)
    print(f"Serving Local Face Photos at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
