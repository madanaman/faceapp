# API Testing

Import the Postman collection at [postman/Local Face Photos.postman_collection.json](../postman/Local%20Face%20Photos.postman_collection.json) to test backend APIs individually.

Useful collection variables:

- `baseUrl`: local server URL, usually `http://127.0.0.1:8000`
- `scanPath`: folder path to scan
- `scanMode`: `photos`, `videos`, or `both`
- `fileId`, `faceId`, `mediaPath`: can be populated by running `GET /api/files` after a scan
- `tagName`: sample person tag for `POST /api/tag`
- `albumId`, `albumName`: sample album values
- `photoTagId`, `photoTagName`: sample descriptive photo-tag values
- `locationLabel`, `locationCity`, `locationRegion`, `locationCountry`: sample manual or scan-time location values
- `backupPath`: folder path for backup/restore tests

Metadata API examples:

```text
/api/search?year=2022
/api/search?city=Toronto
/api/search?region=Ontario
/api/search?country=Canada
/api/search?place=Toronto
/api/search?place=Canada
/api/search?year=2022&city=Toronto
/api/search?album=Malaysia%20Trip
/api/search?tag=Aman%27s%20first%20birthday
```

Location API examples:

```text
GET /api/locations
GET /api/locations/suggest?q=Delhi
POST /api/locations/resolve
POST /api/photos/location
DELETE /api/photos/location
```

Year queries use `photo_metadata.taken_at`. Place queries use `photo_places.city`, `photo_places.region`, and `photo_places.country`. GPS-only photos become searchable by place name after `POST /api/locations/resolve` fills those fields, or after you add a scan-time/manual location.

Backup and restore API examples:

```text
POST /api/backup
POST /api/restore/validate
POST /api/restore
```

`POST /api/backup` accepts `path` and `includeMedia`. Metadata backups copy the local index and thumbnails. Full backups also copy original media into `media/by-id/` and record per-media mappings/checksums in `media-index.jsonl`; `manifest.json` stores the media index pointer and checksum.
