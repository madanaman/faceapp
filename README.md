# Local Face Photos

A small local-first alternative for browsing photos by tagged faces.

## What it does

- Lets you choose a local folder from your computer.
- Recursively scans supported image/video files.
- Uses local `FaceAnalysis(name="buffalo_l", providers=["CoreMLExecutionProvider", "CPUExecutionProvider"])` detection.
- Shows cropped face thumbnails so you can tag people.
- Stores InsightFace embeddings and propagates a tag to matching untagged faces and video face clusters.
- Saves photos, faces, people, tags, EXIF metadata, and place-enrichment fields in a local SQLite file.
- Searches by one person or multiple people in the same file.
- Lets you scan photos, videos, or both, and hides videos with no taggable faces by default.

## Privacy model

Files are read locally from the folder you choose. The app does not upload photos anywhere and does not need a cloud account. The SQLite index and generated video face thumbnails stay in this project folder.

## Local engine

The server expects your `faceapp`/InsightFace environment. It prefers CoreML and falls back to CPU:

```py
FaceAnalysis(name="buffalo_l", providers=["CoreMLExecutionProvider", "CPUExecutionProvider"])
```

The default auto-tag similarity threshold is `0.42`. You can tune it:

```sh
FACE_MATCH_THRESHOLD=0.5 /opt/homebrew/Caskroom/miniforge/base/envs/faceapp/bin/python server.py
```

Supported file suffixes are configured in `backend/config.py`:

- Images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.heic`, `.heif`
- Videos: `.mp4`, `.mov`, `.m4v`, `.avi`, `.webm`

HEIC/HEIF support depends on the local Pillow build. Some video codecs may not decode through OpenCV; those files are skipped with scan warnings instead of stopping the whole scan.

## Video scanning

Video scans sample frames instead of reading every frame. Faces are filtered by InsightFace detection score and minimum face size, clustered by embedding similarity, and represented in the UI by the best face crop. Generated video thumbnails are stored under `.thumbnails/`, which is ignored by git.

Video tuning environment variables:

```sh
VIDEO_SAMPLE_INTERVAL_SECONDS=3
VIDEO_MAX_FRAMES=300
VIDEO_MIN_DETECTION_SCORE=0.7
VIDEO_MIN_FACE_HEIGHT_RATIO=0.04
VIDEO_CLUSTER_THRESHOLD=0.42
```

Long videos can still take a while, especially on CPU fallback. Videos do not yet extract MP4/MOV creation timestamps into `photo_metadata.taken_at`, so date sorting and year filters are currently strongest for photos.

## Run

From this folder:

```sh
./run.sh
# or
make run
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
- `face_clusters`: video face cluster metadata and representative faces.
- `people`: canonical person names.
- `face_people`: manual or auto-propagated face/person links.
- `ignored_faces`: face boxes/embeddings hidden from future scans.
- `photo_metadata`: EXIF-derived `taken_at`, camera details, GPS, orientation, raw EXIF JSON.
- `photo_places`: human place names such as city/region/country for later reverse-geocoding enrichment.

Year queries use `photo_metadata.taken_at`. City queries use `photo_places.city`, so GPS-only photos need a future reverse-geocoding enrichment step before natural place searches like `Toronto` become reliable.
