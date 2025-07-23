# Project Repository

This is the backend API for subtitle/audio sync.  

## Configuring Upload Size Limits

**Large File Uploads / 413 Payload Too Large errors**  
- By default, the backend allows uploads up to **1GB** each for video/subtitle files.
- To allow larger (or smaller) files, set the environment variable `MAX_UPLOAD_SIZE_MB` before starting the backend:
  ```
  export MAX_UPLOAD_SIZE_MB=2048    # Set to 2GB, for example
  ```
- If you encounter `413 Payload Too Large` errors, adjust the above variable as needed.
- **Note:** If running behind NGINX or another proxy, you may also need to increase that proxy's limit (e.g., `client_max_body_size` in nginx.conf).

## Endpoints:

- **POST /upload** — Upload both video and subtitle files.
- **POST /check_sync** — Check if the subtitles are in sync.
- **POST /fix_sync** — Auto-correct subtitle sync (with optional offset).
- **GET /download?file_id=...** — Download video/subtitle/corrected files.

### Details

- Video formats supported: .mp4, .avi, .mkv, .mov, .webm
- Subtitle formats supported: .srt (primary; .vtt, .ass, .ssa placeholders only)

No authentication required.
