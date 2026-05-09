#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/Caskroom/miniforge/base/envs/faceapp/bin/python}"
exec "$PYTHON_BIN" server.py
