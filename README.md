# Local Face Photos

A local-first photo and video library for finding memories by the people, albums, and tags in them. It scans folders on your own computer, detects faces with InsightFace, lets you tag people, and searches your library without uploading private photos to a cloud service.

This is an early open-source beta for technical users who are comfortable trying unsigned desktop builds or running a local Python app.

![Local Face Photos demo](docs/assets/faceapp-demo.gif)

## Download

The current public build is available from the GitHub release page:

- [Download Local Face Photos v1.1.0 beta for macOS Apple Silicon](https://github.com/madanaman/faceapp/releases/download/v1.1.0-beta.1/Local.Face.Photos_0.1.0_aarch64.dmg)
- Release page: [v1.1.0-beta.1](https://github.com/madanaman/faceapp/releases/tag/v1.1.0-beta.1)
- SHA-256: `e8bae529b740b9e87db12cfacdddbd7d337d98b418ddd72bc90395e1bd2f15e0`

Important beta notes:

- macOS Apple Silicon only for now.
- The app is unsigned and not notarized yet. On macOS, you may need to right-click the app and choose **Open** the first time.
- First launch can take a minute while the local face engine starts.
- Large video scans can be slow, especially on CPU fallback.

## Why This Exists

Google Photos and similar services are convenient, but they often push users toward paid cloud storage. Local Face Photos is an experiment in keeping the useful parts of photo search while keeping the actual media, face embeddings, tags, and index on your own machine.

## What It Can Do

- Scan local folders recursively for supported photos and videos.
- Detect faces locally with InsightFace `buffalo_l`.
- Tag people from cropped face thumbnails.
- Auto-propagate tags to matching untagged faces.
- Cluster repeated faces in videos so one person is not shown dozens of times.
- Search by one person, multiple people, albums, or descriptive photo tags.
- Filter by media type, year, month, date, and sort direction.
- Add albums during scan, or later per photo/video.
- Hide videos with no visible/taggable faces by default.
- Ignore/remove noisy face boxes so they stay hidden on future scans.
- Store the index locally in SQLite.

## Privacy Model

Local Face Photos does not upload photos, videos, embeddings, tags, or metadata to a cloud service. The desktop app starts a local backend on your computer, reads the folders you choose, runs face detection locally, and stores the generated index locally.

Please do not attach private photos, face crops, databases, or full personal file paths to public GitHub issues. Use synthetic examples or redact sensitive details.

Packaged desktop builds store generated app data outside the source folder:

- macOS: `~/Library/Application Support/Local Face Photos`
- Windows: `%APPDATA%\Local Face Photos`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/local-face-photos`

## Quick Start: Desktop App

1. Download the DMG from the latest release.
2. Open the DMG and drag **Local Face Photos** to Applications.
3. Launch the app. If macOS blocks it because it is unsigned, right-click the app and choose **Open**.
4. Click **Choose Folder** and select a folder with demo or personal media.
5. Choose whether to scan **Photos**, **Videos**, or **Both**.
6. Optionally enter an album name before scanning.
7. Tag a few detected faces, then search by name, album, or photo tag.

## Quick Start: Local Web App

Use this path if you want to run from source.

Requirements:

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

Run the app:

```sh
./run.sh
# or
make run
```

Then open:

```text
http://localhost:8000
```

Apple Silicon users may prefer a Conda/Miniforge environment for CoreML/ONNX packages. If you use a custom interpreter, set `PYTHON_BIN` when running commands:

```sh
PYTHON_BIN=/path/to/python make run
```

On Windows, use Python 3.11 x64 if possible. Install Microsoft C++ Build Tools if Python packages need to compile native wheels.

## Search Examples

```text
Alex
Alex, Jordan
Mary Smith
Malaysia Trip
Aman's first birthday
Alex, Malaysia Trip
```

Search terms can match people, albums, or descriptive photo tags. Multiple terms use comma-separated AND matching, so `Alex, Malaysia Trip` returns files where both match.

Metadata API examples:

```text
/api/search?year=2022
/api/search?city=Toronto
/api/search?year=2022&city=Toronto
/api/search?album=Malaysia%20Trip
/api/search?tag=Aman%27s%20first%20birthday
```

Year queries use `photo_metadata.taken_at`. City queries use `photo_places.city`, so GPS-only photos need a future reverse-geocoding enrichment step before natural place searches like `Toronto` become reliable.

## Supported Files

Supported suffixes are configured in [backend/config.py](backend/config.py):

- Images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.heic`, `.heif`
- Videos: `.mp4`, `.mov`, `.m4v`, `.avi`, `.webm`

HEIC/HEIF support depends on your local Pillow build. Some video codecs may not decode through OpenCV; those files are skipped with scan warnings instead of stopping the whole scan.

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
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=3
```

Backend logs are written to `logs/faceapp.log` with daily rotation. Use `LOG_LEVEL=DEBUG` when you need per-file scan and detection detail.

`INSIGHTFACE_PROVIDERS` is optional. By default macOS uses `CoreMLExecutionProvider,CPUExecutionProvider`; Windows and Linux use `CPUExecutionProvider`. For Windows CPU testing you can leave it unset or set:

```sh
INSIGHTFACE_PROVIDERS=CPUExecutionProvider
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

## Desktop Packaging

The desktop build uses Tauri for the shell and PyInstaller for the local Python backend sidecar.

Install desktop build dependencies:

```sh
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt
npm install
```

Build on macOS/Linux:

```sh
python scripts/check.py
python scripts/desktop_build.py
```

Build on Windows PowerShell:

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pip install -r requirements-desktop.txt
npm install
py -3.11 scripts\check.py
py -3.11 scripts\desktop_build.py
```

The build script asks Tauri for the platform bundle target automatically: DMG on macOS, NSIS installer on Windows, and AppImage on Linux. Set `TAURI_BUNDLES=app` on macOS if you only want the raw `.app` bundle during development.

The generated desktop sidecar is intentionally not committed. Each OS must build its own sidecar binary.

## Development

Run the checks:

```sh
make check
```

The test suite intentionally avoids requiring a full InsightFace model download in CI. Heavy runtime testing should be done locally with a small private or synthetic media folder.

## API Testing

Import the Postman collection at [postman/Local Face Photos.postman_collection.json](postman/Local%20Face%20Photos.postman_collection.json) to test backend APIs individually.

Useful collection variables:

- `baseUrl`: local server URL, usually `http://127.0.0.1:8000`
- `scanPath`: folder path to scan
- `scanMode`: `photos`, `videos`, or `both`
- `fileId`, `faceId`, `mediaPath`: can be populated by running `GET /api/files` after a scan
- `tagName`: sample person tag for `POST /api/tag`
- `albumId`, `albumName`: sample album values
- `photoTagId`, `photoTagName`: sample descriptive photo-tag values

## Roadmap

- Intel Mac build and wider platform packaging.
- Signed and notarized macOS releases.
- Better video timestamp extraction from container metadata.
- Optional reverse geocoding for city/region search.
- More polished demo media and onboarding.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
