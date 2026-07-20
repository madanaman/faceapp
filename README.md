# Local Face Photos

A private, local-first photo and video library for finding memories by the people, albums, tags, dates, and simple natural-language queries.

Local Face Photos scans folders on your own computer, detects faces with InsightFace, lets you tag people, and searches your library without uploading private photos to a cloud service. Searches like `show me photos of Aman from 2022` are interpreted locally against your own people, albums, and photo tags.

This is an early open-source beta for technical users who are comfortable trying unsigned desktop builds or running a local Python app.

![Local Face Photos demo](docs/assets/faceapp-demo.gif)

## Download

The current public build is available from the GitHub release page:

- [Download the latest tested macOS Apple Silicon beta](https://github.com/madanaman/faceapp/releases/latest)
- Current release: [v1.2.0-beta.1](https://github.com/madanaman/faceapp/releases/tag/v1.2.0-beta.1)
- Current Apple Silicon DMG SHA-256: `c99af47122359d3ad82bbb59a1d23301c9b2319a5f4b2ec1c81311d09761d1b5`
- Experimental Intel Mac x64 builds can be generated from GitHub Actions, but they are community-test candidates until validated on real Intel hardware.

Important beta notes:

- The Apple Silicon DMG is the currently tested desktop build.
- The app is unsigned and not notarized yet. On macOS, you may need to right-click the app and choose **Open** the first time.
- First launch can take a minute while the local face engine starts.
- Large video scans can be slow, especially on CPU fallback.

## Why This Exists

Google Photos and similar services are convenient, but they often push users toward paid cloud storage. Local Face Photos is an experiment in keeping the useful parts of photo search while keeping the actual media, face embeddings, tags, and index on your own machine.

Google Takeout can get your photos back onto your computer. The bigger question is: **now what?**

This project is one answer to that question.

## Quick Start

### Option A: Try With Demo Media

If you do not want to scan personal photos right away, download the provided [synthetic demo media pack](docs/demo-media/local-face-photos-demo-media.zip).

1. Download and unzip the demo media pack.
2. Launch Local Face Photos.
3. Click **Choose Folder** and select the demo media folder.
4. Set **Scan** to **Both**.
5. Enter an album name such as `Demo Album`.
6. Click **Scan Path**.
7. Tag a few detected faces with names like `Aman`, `Preeti`, `Sahil`, and `Sofia`.
8. Try searches like `show me videos with Aman from December 2022`, `photos from 2022`, `Aman`, `Aman, Preeti`, `Demo Album`, or `birthday`.

The demo media is synthetic and does not contain private family photos.

### Option B: Scan Your Own Library

1. Download the DMG from the latest release.
2. Open the DMG and drag **Local Face Photos** to Applications.
3. Launch the app. If macOS blocks it because it is unsigned, right-click the app and choose **Open**.
4. Click **Choose Folder** and select a folder with photos or videos.
5. Choose whether to scan **Photos**, **Videos**, or **Both**.
6. Optionally enter an album name before scanning.
7. Tag a few detected faces, then search by name, album, date, photo tag, or a simple sentence.

## What It Can Do

- Scan local folders recursively for supported photos and videos.
- Detect faces locally with InsightFace `buffalo_l`.
- Tag people from cropped face thumbnails.
- Auto-propagate tags to matching untagged faces.
- Cluster repeated faces in videos so one person is not shown dozens of times.
- Search by one person, multiple people, albums, or descriptive photo tags.
- Interpret simple natural-language searches offline, using your local people, albums, tags, and date filters.
- Filter by media type, year, month, date, and sort direction.
- Add albums during scan, or later per photo/video.
- Hide videos with no visible/taggable faces by default.
- Ignore/remove noisy face boxes so they stay hidden on future scans.
- Store the index locally in SQLite.

## Privacy Model

Local Face Photos does not upload photos, videos, embeddings, tags, or metadata to a cloud service. The desktop app starts a local backend on your computer, reads the folders you choose, runs face detection locally, and stores the generated index locally.

Packaged desktop builds store generated app data outside the source folder:

- macOS: `~/Library/Application Support/Local Face Photos`
- Windows: `%APPDATA%\Local Face Photos`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/local-face-photos`

Please do not attach private photos, face crops, databases, or full personal file paths to public GitHub issues. Use synthetic examples or redact sensitive details.

## Search Examples

```text
Alex
Alex, Jordan
Mary Smith
Ironman Malaysia
Aman's first birthday
Alex, Ironman Malaysia
photos from 2022
December 2022
show me photos of Alex from 2022
show videos with Alex and Jordan from December 2022
show me Alex's first birthday photos from Ironman Malaysia
```

Search terms can match people, albums, or descriptive photo tags. Multiple terms use comma-separated AND matching, so `Alex, Ironman Malaysia` returns files where both match.

Natural-language search is currently an offline parser, not an external AI call. It works best after you have tagged people and added albums or photo tags, because it matches your words against the local index. Unknown words are ignored rather than sent anywhere.

## Use of Codex and GPT-5.6

Codex was used as a development collaborator throughout the project: planning the architecture, refactoring the backend, designing the SQLite schema, adding video support, creating tests, packaging the app with Tauri, preparing GitHub releases, and polishing documentation.

The app now includes a local first-pass natural-language parser for searches like:

- “Show me photos of Aman from 2022”
- “Find Ironman Malaysia photos with Preeti”
- “Show videos from December 2022”

GPT-5.6 is planned as a future optional layer for richer query understanding. The goal is to keep the private photo library local while using OpenAI, when enabled by the user, only to translate human search intent into structured local database queries.

## Documentation

- [Installation and local development](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Architecture and local data](docs/architecture.md)
- [Video scanning](docs/video-scanning.md)
- [Desktop packaging](docs/desktop-packaging.md)
- [API testing with Postman](docs/api-testing.md)
- [Roadmap](docs/roadmap.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
