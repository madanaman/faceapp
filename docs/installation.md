# Installation and Local Development

Use the desktop build if you only want to try the app. Use the local web app path if you want to develop, debug, or run from source.

## Desktop App

1. Download the DMG from the [latest release](https://github.com/madanaman/faceapp/releases/latest).
2. Open the DMG and drag **Local Face Photos** to Applications.
3. Launch the app. If macOS blocks it because it is unsigned, right-click the app and choose **Open**.
4. Click **Choose Folder** and scan a demo or personal media folder.

## Local Web App

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

## Supported Files

Supported suffixes are configured in [backend/config.py](../backend/config.py):

- Images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.heic`, `.heif`
- Videos: `.mp4`, `.mov`, `.m4v`, `.avi`, `.webm`

HEIC/HEIF support depends on your local Pillow build. Some video codecs may not decode through OpenCV; those files are skipped with scan warnings instead of stopping the whole scan.

## Demo Media

The repo includes a [synthetic demo media pack](demo-media/local-face-photos-demo-media.zip) so reviewers and new users can try scanning, tagging, album assignment, and search without using personal photos.
