# Local Face Photos

A local-first photo and video library for finding memories by the people in them. It scans folders on your own computer, detects faces with InsightFace/InsightEdge, lets you tag people, and searches by one or more names.

This is an early open-source build aimed at technical users. It runs as a local web app today; Docker and desktop packaging are planned for later releases.

## Features

- Scan local folders recursively for supported images and videos.
- Detect faces locally with `FaceAnalysis(name="buffalo_l", providers=["CoreMLExecutionProvider", "CPUExecutionProvider"])`.
- Tag people from cropped face thumbnails.
- Auto-propagate tags to matching untagged faces.
- Cluster repeated faces in videos so one person is not shown dozens of times.
- Search by one person or multiple people in the same file.
- Filter by media type, year, month, date, and sort direction.
- Hide videos with no visible/taggable faces by default.
- Ignore/remove noisy face boxes so they stay hidden on future scans.
- Store the index locally in SQLite.

## Privacy Model

Local Face Photos does not upload photos, videos, embeddings, tags, or metadata to a cloud service. The server reads files from paths you provide, runs detection locally, and stores the index in this project folder.

Please do not attach private photos, face crops, databases, or full personal file paths to public GitHub issues. Use synthetic examples or redact sensitive details.

## Supported Files

Supported suffixes are configured in [backend/config.py](backend/config.py):

- Images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.heic`, `.heif`
- Videos: `.mp4`, `.mov`, `.m4v`, `.avi`, `.webm`

HEIC/HEIF support depends on your local Pillow build. Some video codecs may not decode through OpenCV; those files are skipped with scan warnings instead of stopping the whole scan.

## Requirements

- Python 3.11+
- Node.js 20+ for frontend contract tests
- InsightFace or InsightEdge runtime dependencies
- ONNX Runtime
- OpenCV

Install Python dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Apple Silicon users may prefer a Conda/Miniforge environment for CoreML/ONNX packages. If you use a custom interpreter, set `PYTHON_BIN` when running commands:

```sh
PYTHON_BIN=/path/to/python make run
```

## Run

```sh
./run.sh
# or
make run
```

Then open:

```text
http://localhost:8000
```

Enter a local folder path in the UI and choose whether to scan photos, videos, or both.

## Search Examples

```text
Alex
Alex, Jordan
Mary Smith
```

Multiple names use comma-separated AND matching, so `Alex, Jordan` returns files where both names appear.

Metadata API examples:

```text
/api/search?year=2022
/api/search?city=Toronto
/api/search?year=2022&city=Toronto
```

Year queries use `photo_metadata.taken_at`. City queries use `photo_places.city`, so GPS-only photos need a future reverse-geocoding enrichment step before natural place searches like `Toronto` become reliable.

## Configuration

Copy [.env.example](.env.example) if you want a place to track local settings. The app reads environment variables from your shell; it does not auto-load `.env` files yet.

Common tuning variables:

```sh
FACE_MATCH_THRESHOLD=0.42
FACE_RECONCILE_THRESHOLD=0.85
FACE_BOX_IOU_THRESHOLD=0.7
INSIGHTFACE_MODEL=buffalo_l
VIDEO_SAMPLE_INTERVAL_SECONDS=3
VIDEO_MAX_FRAMES=300
VIDEO_MIN_DETECTION_SCORE=0.7
VIDEO_MIN_FACE_HEIGHT_RATIO=0.04
VIDEO_CLUSTER_THRESHOLD=0.42
```

## Video Scanning

Video scans sample frames instead of reading every frame. Faces are filtered by InsightFace detection score and minimum face size, clustered by embedding similarity, and represented in the UI by the best face crop.

Generated video face thumbnails are stored under `.thumbnails/`, which is ignored by git. Long videos can still take a while, especially on CPU fallback.

Known limitation: videos do not yet extract MP4/MOV creation timestamps into `photo_metadata.taken_at`, so date sorting and year filters are currently strongest for photos.

## Local Data

Generated files are intentionally ignored by git:

- `face_index.sqlite3`
- `face_index.sqlite3-wal`
- `face_index.sqlite3-shm`
- `.thumbnails/`
- `.cache/`

The SQLite database is normalized for future queries:

- `photos`: file identity, dimensions, signature, indexed timestamp.
- `faces`: face boxes and embeddings linked to photos.
- `face_clusters`: video face cluster metadata and representative faces.
- `people`: canonical person names.
- `face_people`: manual or auto-propagated face/person links.
- `ignored_faces`: face boxes/embeddings hidden from future scans.
- `photo_metadata`: EXIF-derived `taken_at`, camera details, GPS, orientation, raw EXIF JSON.
- `photo_places`: human place names such as city/region/country for future reverse-geocoding enrichment.

## Development

Run the checks:

```sh
make check
```

The test suite intentionally avoids requiring a full InsightFace model download in CI. Heavy runtime testing should be done locally with a small private or synthetic media folder.

## Roadmap

- Docker-first distribution for technical users.
- Desktop packaging with folder picker and bundled backend.
- Better video timestamp extraction from container metadata.
- Optional reverse geocoding for city/region search.
- Sample/demo media that does not contain private photos.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
