# Video Scanning

Video support exists because so many memories are hiding inside short clips, not just photos.

Video scans sample frames instead of reading every frame. Faces are filtered by InsightFace detection score and minimum face size, clustered by embedding similarity, and represented in the UI by the best face crop.

Generated video face thumbnails are stored under `.thumbnails/`, which is ignored by git.

Long videos can still take a while, especially on CPU fallback. The current strategy is intentionally practical rather than perfect:

- sample frames at a configurable interval
- skip low-confidence/background detections where possible
- cluster repeated appearances of the same person
- show representative thumbnails for tagging
- preserve scan warnings instead of crashing on codec issues

Known limitation: videos do not yet extract MP4/MOV creation timestamps into `photo_metadata.taken_at`, so date sorting and year filters are currently strongest for photos.
