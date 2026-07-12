from __future__ import annotations

import os

os.environ.setdefault("LOCAL_FACE_PACKAGED", "1")
os.environ.setdefault("LOCAL_FACE_HOST", "127.0.0.1")
os.environ.setdefault("LOCAL_FACE_PORT", "8000")

from server import main


if __name__ == "__main__":
    main()
