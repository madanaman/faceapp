# Security Policy

## Supported Versions

This project is pre-1.0. Security fixes should target the default branch unless a release branch exists.

## Reporting a Vulnerability

Please open a private report or contact the maintainer before posting sensitive details publicly.

Do not attach:

- private photos or videos
- face crops
- SQLite database files
- generated thumbnails
- unredacted local file paths

## Privacy Expectations

Local Face Photos is designed to run locally. It does not intentionally upload photos, videos, embeddings, metadata, or tags to any external service.

Important caveats:

- The app reads files from paths you provide.
- The SQLite database contains face embeddings, tags, file paths, and metadata.
- Generated thumbnails may contain cropped faces from videos.
- If you share logs or screenshots, review them for personal paths and private media first.
