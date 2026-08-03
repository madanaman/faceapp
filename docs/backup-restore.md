# Backup and Restore

Local Face Photos supports folder-based backups. The folder can be on an external drive or inside a cloud-synced folder such as iCloud Drive, Google Drive, OneDrive, or Dropbox.

## Backup Modes

- **Metadata backup** copies the SQLite index, generated thumbnails, and `manifest.json`. Original media stays at its existing paths.
- **Full backup** copies the SQLite index, generated thumbnails, `manifest.json`, `media-index.jsonl`, and original media files into `media/by-id/`.

The manifest records the backup format version, timestamp, database checksum, thumbnail counts, media counts, and a checksum pointer to `media-index.jsonl`. Detailed per-photo media mappings live in `media-index.jsonl` so large libraries do not produce a huge manifest file.

Each line in `media-index.jsonl` is one JSON object containing the photo ID, original path, backed-up media path, size, and checksum.

## Restore Behavior

Restore copies data into the app's local data folder. The app does not run directly from the backup folder.

- Metadata restore keeps the original media paths from the restored database.
- Full restore copies backed-up media into app-managed `restored-media/` storage and rewrites `photos.path` to those restored files.
- If a full backup is missing individual media files, restore continues with a warning. Metadata, thumbnails, and available media are restored; missing media may not open until the original file is available again.

Before restore, the app creates a safety copy of the current database under `restore-safety/`.

## Current Limits

- Cloud provider APIs are not integrated yet. Use a cloud-synced folder as the backup target.
- Backup is full-copy, not incremental.
- Backup encryption is not included in V1.
