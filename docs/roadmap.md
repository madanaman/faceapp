# Roadmap

This is still an early beta. The next useful steps are less about adding noise and more about making the app easier to try, easier to package, and easier to search naturally.

Current roadmap:

- Location based media search:
  - Search by known city, region, or country stored in the local index.
  - Add optional reverse geocoding for GPS-only photos.
  - Add UI controls for reviewing and correcting places.
- Backup and restore to external folder:
  - V1 supports metadata and full folder backups with a checksum manifest.
  - V1 restores the local index, thumbnails, and optionally copied media.
  - Future work: scheduled backups while the app is open, with daily/weekly/monthly options.
  - Future work: incremental backups, encryption, and conflict handling.
- Multi-profile local users:
  - Add local profiles for separate users/libraries on one computer.
  - Scope people, albums, tags, ignored faces, and settings by library/profile.
  - Keep this separate from internet login/auth for now.
- Cloud provider integration:
  - Start with cloud-synced folders as backup targets.
  - Later add provider APIs such as iCloud Drive, Google Drive, OneDrive, or Dropbox.
  - Keep cloud integration optional and explicit.
- Intel Mac validation and wider platform packaging.
- Windows desktop build.
- Signed and notarized macOS releases.
- Better video timestamp extraction from container metadata.
- Stronger OpenAI-powered natural language query understanding.
- More polished onboarding and demo media.

Open roadmap issues live in the [GitHub issue tracker](https://github.com/madanaman/faceapp/issues).
