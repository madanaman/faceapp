# Architecture and Local Data

Local Face Photos is built around a local Python backend, a browser-style frontend, a SQLite index, and a Tauri desktop shell.

The important design choice is that media stays local. The app stores paths, metadata, face boxes, embeddings, albums, and tags in a local SQLite database so searches can be fast without sending private photos elsewhere.

## Local Data

Generated files are intentionally ignored by git:

- `face_index.sqlite3`
- `face_index.sqlite3-wal`
- `face_index.sqlite3-shm`
- `.thumbnails/`
- `.cache/`

Packaged desktop builds store generated app data outside the source folder:

- macOS: `~/Library/Application Support/Local Face Photos`
- Windows: `%APPDATA%\Local Face Photos`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/local-face-photos`

## Database Shape

The SQLite database is normalized for future queries:

- `photos`: file identity, dimensions, signature, indexed timestamp.
- `faces`: face boxes and embeddings linked to photos.
- `face_clusters`: video face cluster metadata and representative faces.
- `people`: canonical person names.
- `face_people`: manual or auto-propagated face/person links.
- `ignored_faces`: face boxes/embeddings hidden from future scans.
- `photo_metadata`: EXIF-derived `taken_at`, camera details, GPS, orientation, raw EXIF JSON.
- `photo_places`: human place names such as city/region/country for future reverse-geocoding enrichment.

## Architecture Diagram

- [High-level architecture flow](assets/high_level_architecture_flow.png)
- [Editable draw.io architecture diagram](assets/architecture_flow.drawio)
