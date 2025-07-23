# Project Repository

This is the backend API for subtitle/audio sync.  
## Endpoints:

- **POST /upload** — Upload both video and subtitle files.
- **POST /check_sync** — Check if the subtitles are in sync.
- **POST /fix_sync** — Auto-correct subtitle sync (with optional offset).
- **GET /download?file_id=...** — Download video/subtitle/corrected files.

### Details

- Video formats supported: .mp4, .avi, .mkv, .mov, .webm
- Subtitle formats supported: .srt (primary; .vtt, .ass, .ssa placeholders only)

No authentication required.
