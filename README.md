# Local Face Photos

A small local-first alternative for browsing photos by tagged faces.

## What it does

- Lets you choose a local folder from your computer.
- Recursively scans supported image/video files.
- Uses local `FaceAnalysis(name="buffalo_l", providers=["CoreMLExecutionProvider", "CPUExecutionProvider"])` detection.
- Shows cropped face thumbnails so you can tag people.
- Stores InsightFace embeddings and propagates a tag to matching untagged faces.
- Saves photos, faces, people, tags, EXIF metadata, and place-enrichment fields in a local SQLite file.
- Searches by one person or multiple people in the same file.

## Privacy model

Files are read by the browser from the folder you choose. The app does not upload photos anywhere and does not need a cloud account.

## Browser support

The server expects your `faceapp`/InsightFace environment. It prefers CoreML and falls back to CPU:

```py
FaceAnalysis(name="buffalo_l", providers=["CoreMLExecutionProvider", "CPUExecutionProvider"])
```

The default auto-tag similarity threshold is `0.42`. You can tune it:

```sh
FACE_MATCH_THRESHOLD=0.5 /opt/homebrew/Caskroom/miniforge/base/envs/faceapp/bin/python server.py
```

## Run

From this folder:

```sh
/opt/homebrew/Caskroom/miniforge/base/envs/faceapp/bin/python server.py
```

Then open:

```text
http://localhost:8000
```

Search examples:

```text
Aman
Aman, Mom
Aman Mom
```

Metadata API examples:

```text
/api/search?year=2022
/api/search?city=Toronto
/api/search?year=2022&city=Toronto
```

## Database shape

The SQLite database is normalized for future queries:

- `photos`: file identity, dimensions, signature, indexed timestamp.
- `faces`: face boxes and embeddings linked to photos.
- `people`: canonical person names.
- `face_people`: manual or auto-propagated face/person links.
- `photo_metadata`: EXIF-derived `taken_at`, camera details, GPS, orientation, raw EXIF JSON.
- `photo_places`: human place names such as city/region/country for later reverse-geocoding enrichment.

Year queries use `photo_metadata.taken_at`. City queries use `photo_places.city`, so GPS-only photos need a future reverse-geocoding enrichment step before natural place searches like `Toronto` become reliable.
