from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import os
import shutil
import tempfile
from .subsync_utils import (
    check_subtitle_sync,
    apply_sync_correction,
    SubtitleFormatError,
)

app = FastAPI(
    title="Subtitle Sync Backend",
    description="APIs for uploading video, subtitle, checking/fixing sync, and downloading the result.",
    version="1.0.0",
    openapi_tags=[
        {"name": "sync", "description": "Endpoints for subtitle sync/processing"},
        {"name": "status", "description": "Health check endpoint"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["status"], summary="Health Check", description="Backend health check endpoint")
def health_check():
    """Health check endpoint for backend."""
    return {"message": "Healthy"}

# Pydantic models
class SyncCheckResponse(BaseModel):
    offset: float = Field(..., description="Offset in seconds needed to sync subtitles. 0 means already in sync.")
    needs_sync: bool = Field(..., description="Whether sync correction is recommended.")
    detail: str = Field(..., description="Human readable analysis.")

class SyncFixResponse(BaseModel):
    result_url: str = Field(..., description="Absolute or relative URL to the corrected subtitle file.")
    detail: str = Field(..., description="Human readable result.")

# Store uploaded files temporarily per session, keyed by upload id
UPLOAD_TMP_DIR = tempfile.gettempdir()  # for demo; in production, secure, persistent location

# PUBLIC_INTERFACE
@app.post("/api/upload", tags=["sync"], summary="Upload a video and subtitle file", description="Upload a video file (any common video type) and a subtitle file (srt/other supported formats).")
async def upload_files(
    video_file: UploadFile = File(..., description="Video file (e.g., mp4, mkv)"),
    subtitle_file: UploadFile = File(..., description="Subtitle file (.srt, .vtt supported)"),
):
    """
    Accepts video and subtitle file uploads, stores them in a tmp folder, returns an upload_id handle for further processing.
    """
    upload_id = next(tempfile._get_candidate_names())
    upload_dir = os.path.join(UPLOAD_TMP_DIR, f"subsync_{upload_id}")
    os.makedirs(upload_dir, exist_ok=True)
    # Save video
    video_path = os.path.join(upload_dir, video_file.filename)
    with open(video_path, "wb") as f:
        shutil.copyfileobj(video_file.file, f)
    # Save subtitle
    subtitle_path = os.path.join(upload_dir, subtitle_file.filename)
    with open(subtitle_path, "wb") as f:
        shutil.copyfileobj(subtitle_file.file, f)
    return {"upload_id": upload_id, "video_filename": video_file.filename, "subtitle_filename": subtitle_file.filename}

# PUBLIC_INTERFACE
@app.post("/api/check_sync", tags=["sync"], response_model=SyncCheckResponse, summary="Check subtitle sync", description="Check if the uploaded subtitle and video are in sync.")
async def check_sync(
    upload_id: str = Form(..., description="Returned ID from /api/upload"),
):
    """
    Checks if the subtitle file for given upload_id is in sync with the video.
    Returns offset in seconds required to align, and a flag if correction is recommended.
    """
    upload_dir = os.path.join(UPLOAD_TMP_DIR, f"subsync_{upload_id}")
    if not os.path.exists(upload_dir):
        return JSONResponse(status_code=404, content={"detail": "Upload session not found"})
    files = os.listdir(upload_dir)
    video_fp = next((os.path.join(upload_dir, f) for f in files if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))), None)
    sub_fp = next((os.path.join(upload_dir, f) for f in files if f.lower().endswith((".srt", ".vtt"))), None)
    if not (video_fp and sub_fp):
        return JSONResponse(status_code=400, content={"detail": "Files missing for this session"})
    try:
        offset = check_subtitle_sync(video_fp, sub_fp)
    except SubtitleFormatError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    needs_sync = abs(offset) > 0.1  # Consider threshold for requiring correction
    return {
        "offset": offset,
        "needs_sync": needs_sync,
        "detail": f"Offset is {offset:.3f} seconds. {'Sync correction recommended.' if needs_sync else 'In sync.'}",
    }

# PUBLIC_INTERFACE
@app.post("/api/fix_sync", tags=["sync"], response_model=SyncFixResponse, summary="Fix subtitle sync", description="Automatically corrects subtitle sync if needed, and returns downloadable result.")
async def fix_sync(
    upload_id: str = Form(..., description="Returned ID from /api/upload"),
):
    """
    Applies automatic sync correction for a session and generates a new subtitle file.
    Returns a URL to download the output.
    """
    upload_dir = os.path.join(UPLOAD_TMP_DIR, f"subsync_{upload_id}")
    if not os.path.exists(upload_dir):
        return JSONResponse(status_code=404, content={"detail": "Upload session not found"})
    files = os.listdir(upload_dir)
    video_fp = next((os.path.join(upload_dir, f) for f in files if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))), None)
    sub_fp = next((os.path.join(upload_dir, f) for f in files if f.lower().endswith((".srt", ".vtt"))), None)
    if not (video_fp and sub_fp):
        return JSONResponse(status_code=400, content={"detail": "Files missing for this session"})
    try:
        offset = check_subtitle_sync(video_fp, sub_fp)
        needs_sync = abs(offset) > 0.1
        if not needs_sync:
            # Already in sync; just provide existing subtitle
            result_fp = sub_fp
            detail = "Already in sync; no correction needed."
        else:
            # Write corrected subtitle to output file
            res_fn = f"synced_{os.path.basename(sub_fp)}"
            result_fp = os.path.join(upload_dir, res_fn)
            apply_sync_correction(sub_fp, offset, result_fp)
            detail = f"Sync correction applied with {offset:.3f} seconds offset."
    except SubtitleFormatError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
    # Return a URL to download the subtitle
    # NOTE: In real deploy, the URL would be properly robust; here just a file-serving endpoint
    return {
        "result_url": f"/api/download/{upload_id}/{os.path.basename(result_fp)}",
        "detail": detail,
    }

# PUBLIC_INTERFACE
@app.get("/api/download/{upload_id}/{filename}", tags=["sync"], summary="Download (corrected) subtitle file")
def download_result(upload_id: str, filename: str):
    """
    Serves the corrected subtitle file for download.
    """
    upload_dir = os.path.join(UPLOAD_TMP_DIR, f"subsync_{upload_id}")
    file_path = os.path.join(upload_dir, filename)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"detail": "Result file not found"})
    # Use FileResponse for direct download
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)
