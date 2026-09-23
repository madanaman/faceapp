# Release Notes

## local-memories-2026-09-22

Status: local release candidate, not yet published as a GitHub release.

Build details:

- Source commit: `4f1de27`
- Platform: macOS Apple Silicon
- Artifact: `Local Face Photos_0.1.0_aarch64.dmg`
- SHA-256: `7119148ad064e566a0d4fce619ed4047fdd022d5bfab99674f33648416844d17`

Changes:

- Added local Memories generation.
- Added Memories sidebar with Generate, Open, and Dismiss actions.
- Added memory types for on-this-day, people over time, albums, photo tags, and places.
- Added SQLite persistence for `memories` and `memory_items`.
- Added backend APIs for listing, generating, and dismissing memories.
- Added regression coverage for memory generation, dismissal, gallery filtering, and HTTP routing.

Validation:

- `python3 scripts/check.py`
- `PYTHON_BIN=/opt/homebrew/Caskroom/miniforge/base/envs/faceapp/bin/python make desktop-build`
- `npm run tauri:build -- --bundles dmg`
