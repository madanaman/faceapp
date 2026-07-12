from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    backend_files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "backend").glob("*.py"))
    run([sys.executable, "-m", "py_compile", "server.py", *backend_files])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"])
    run(["node", "--check", "app.js"])
    test_files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("*.test.mjs"))
    run(["node", "--test", *test_files])


if __name__ == "__main__":
    main()
