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

Metadata API examples:

```text
/api/search?year=2022
/api/search?city=Toronto
/api/search?place=Toronto
/api/search?place=Canada
/api/search?year=2022&city=Toronto
/api/search?album=Malaysia%20Trip
/api/search?tag=Aman%27s%20first%20birthday
```

Year queries use `photo_metadata.taken_at`. City queries use `photo_places.city`, so GPS-only photos need a future reverse-geocoding enrichment step before natural place searches like `Toronto` become reliable.
