# Configuration

Copy [.env.example](../.env.example) if you want a place to track local settings. The app reads environment variables from your shell; it does not auto-load `.env` files yet.

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
LOCATION_REVERSE_GEOCODING_ENABLED=1
LOCATION_REVERSE_GEOCODER=nominatim
LOCATION_GEOCODER_THROTTLE_SECONDS=1.1
LOCATION_RESOLVE_LIMIT=50
LOCATION_SUGGEST_LIMIT=6
LOCATION_CACHE_PRECISION=3
LOCATION_NOMINATIM_SEARCH_URL=https://nominatim.openstreetmap.org/search
LOCATION_NOMINATIM_USER_AGENT="LocalFacePhotos/0.1 local-first photo library"
```

Backend logs are written to `logs/faceapp.log` with daily rotation. Use `LOG_LEVEL=DEBUG` when you need per-file scan and detection detail.

Location resolution is only triggered when the user clicks **Resolve GPS**. The app checks the local `location_cache` first, then calls the configured reverse geocoder for uncached coordinates. Set `LOCATION_REVERSE_GEOCODING_ENABLED=0` to disable online lookups.

`INSIGHTFACE_PROVIDERS` is optional. By default macOS uses `CoreMLExecutionProvider,CPUExecutionProvider`; Windows and Linux use `CPUExecutionProvider`.

For Windows CPU testing you can leave it unset or set:

```sh
INSIGHTFACE_PROVIDERS=CPUExecutionProvider
```
