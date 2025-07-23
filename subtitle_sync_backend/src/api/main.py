import os
import shutil
import tempfile
from typing import Optional, Tuple, List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uuid

app = FastAPI(
    title="Subtitle Sync Tool API",
    description="Backend API for uploading, analyzing, and correcting subtitle and video file sync issues.",
    version="1.0.0",
    openapi_tags=[
        {"name": "sync", "description": "Endpoints to upload files, check and fix subtitle sync, and download outputs."}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open for frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File storage configuration (temporary for this example)
TEMP_DIR = tempfile.gettempdir()
WORKING_DIR = os.path.join(TEMP_DIR, "subtitle_sync_backend")
os.makedirs(WORKING_DIR, exist_ok=True)

SUPPORTED_SUBTITLE_FORMATS = [".srt", ".vtt", ".ass", ".ssa"]
SUPPORTED_VIDEO_FORMATS = [".mp4", ".mkv", ".avi", ".mov", ".webm"]

# Utilities

# PUBLIC_INTERFACE
def allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
    """Utility to check allowed file extension."""
    return any(filename.lower().endswith(ext) for ext in allowed_extensions)

# PUBLIC_INTERFACE
def save_upload_file(upload_file: UploadFile, target_folder: str, prefix="") -> str:
    """Save UploadFile to disk and return full path."""
    extension = os.path.splitext(upload_file.filename)[1]
    filename = f"{prefix}{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(target_folder, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path

# Subtitle sync logic placeholder imports & helpers
import re

# PUBLIC_INTERFACE
def detect_subtitle_format(path: str) -> str:
    """Guess subtitle format based on extension and data."""
    extension = os.path.splitext(path)[1].lower()
    if extension in SUPPORTED_SUBTITLE_FORMATS:
        return extension
    raise ValueError("Unsupported subtitle format")

# PUBLIC_INTERFACE
def parse_srt_times(line: str) -> Optional[Tuple[float, float]]:
    """
    Returns (start time, end time) in seconds for a .srt timecode line, or None if not a timecode.
    SRT: 00:00:10,500 --> 00:00:12,000
    """
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", line)
    if not match:
        return None
    sh, sm, ss, sms, eh, em, es, ems = map(int, match.groups())
    start = sh * 3600 + sm * 60 + ss + sms / 1000
    end = eh * 3600 + em * 60 + es + ems / 1000
    return (start, end)

# PUBLIC_INTERFACE
def estimate_sync_offset(srt_path: str) -> float:
    """
    Estimate sync offset value (in seconds) needed, based on SRT timing.
    Returns: Estimated offset (float), positive if subs are late.
    """
    # This dummy implementation just checks the first two subtitle entries and assumes
    # the first line is too early/late if it starts at 0 or a negative time.
    # In real app you would use voice activity or forced alignments.
    with open(srt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    time_lines = [parse_srt_times(l) for l in lines if parse_srt_times(l)]
    if not time_lines:
        raise ValueError("No timecode lines found in SRT.")
    first_start = time_lines[0][0]
    # Heuristic: If first_start < 0.5, usually should be delayed.
    offset = 2.0 - first_start  # Example: want to start at 2 sec.
    # Cap adjustment to no more than 5s either way
    return min(5.0, max(-5.0, offset))

# PUBLIC_INTERFACE
def apply_srt_offset(input_path: str, output_path: str, offset: float) -> int:
    """
    Apply offset (in seconds) to all subtitle times in an SRT file.
    Returns: number of subtitles changed.
    """
    changed_count = 0
    with open(input_path, "r", encoding="utf-8") as src, open(output_path, "w", encoding="utf-8") as out:
        for line in src:
            parsed = parse_srt_times(line)
            if parsed:
                start, end = parsed
                new_start = max(0, start + offset)
                new_end = max(0, end + offset)
                ns = int(new_start // 3600), int((new_start % 3600) // 60), int(new_start % 60), int((new_start * 1000) % 1000)
                ne = int(new_end // 3600), int((new_end % 3600) // 60), int(new_end % 60), int((new_end * 1000) % 1000)
                out.write("{:02}:{:02}:{:02},{:03} --> {:02}:{:02}:{:02},{:03}\n".format(*ns, *ne))
                changed_count += 1
            else:
                out.write(line)
    return changed_count

# Pydantic models

class UploadResponse(BaseModel):
    message: str = Field(..., description="Status message.")
    video_file_id: str = Field(..., description="ID for uploaded video file (use in further requests).")
    subtitle_file_id: str = Field(..., description="ID for uploaded subtitle file (use in further requests).")

class SyncCheckRequest(BaseModel):
    video_file_id: str = Field(..., description="ID of uploaded video file.")
    subtitle_file_id: str = Field(..., description="ID of uploaded subtitle file.")

class SyncCheckResponse(BaseModel):
    is_synced: bool = Field(..., description="Whether subtitles are synced to video.")
    recommended_offset: Optional[float] = Field(None, description="Offset (seconds) needed to sync, if any.")
    details: Optional[str] = Field(None, description="Extra info.")

class SyncFixRequest(BaseModel):
    video_file_id: str = Field(..., description="ID of uploaded video file.")
    subtitle_file_id: str = Field(..., description="ID of uploaded subtitle file.")
    offset: Optional[float] = Field(None, description="Offset to apply (in seconds). If not specified, auto-detect.")

class SyncFixResponse(BaseModel):
    corrected_subtitle_file_id: str = Field(..., description="ID for newly corrected subtitle file.")
    used_offset: float = Field(..., description="Offset applied in seconds.")
    message: Optional[str] = Field(None, description="Status message.")

# In-memory records (for demo, use persistent storage in production!)
storage_index = {}

# PUBLIC_INTERFACE
@app.post("/upload", summary="Upload video and subtitle files", tags=["sync"], response_model=UploadResponse)
async def upload_files(
    video_file: UploadFile = File(..., description="Video file"),
    subtitle_file: UploadFile = File(..., description="Subtitle file (.srt, .vtt, etc.)"),
):
    """
    Upload both video and subtitle files. Stores them with unique IDs for subsequent operations.
    """
    # Validate video
    if not allowed_file(video_file.filename, SUPPORTED_VIDEO_FORMATS):
        raise HTTPException(status_code=400, detail="Unsupported video format.")
    if not allowed_file(subtitle_file.filename, SUPPORTED_SUBTITLE_FORMATS):
        raise HTTPException(status_code=400, detail="Unsupported subtitle format.")

    vid_id = uuid.uuid4().hex
    sub_id = uuid.uuid4().hex

    vid_path = save_upload_file(video_file, WORKING_DIR, f"video_{vid_id}_")
    sub_path = save_upload_file(subtitle_file, WORKING_DIR, f"sub_{sub_id}_")
    storage_index[vid_id] = vid_path
    storage_index[sub_id] = sub_path

    return UploadResponse(
        message="Files uploaded successfully.",
        video_file_id=vid_id,
        subtitle_file_id=sub_id
    )

# PUBLIC_INTERFACE
@app.post("/check_sync", summary="Check subtitle sync against video", tags=["sync"], response_model=SyncCheckResponse)
async def check_sync(request: SyncCheckRequest):
    """
    Analyze provided video and subtitle for sync status.
    Uses heuristics (based on subtitle content only for now).
    """
    # Validate existence
    sub_path = storage_index.get(request.subtitle_file_id)
    vid_path = storage_index.get(request.video_file_id)
    if not sub_path or not os.path.exists(sub_path):
        raise HTTPException(status_code=404, detail="Subtitle file ID not found.")
    if not vid_path or not os.path.exists(vid_path):
        raise HTTPException(status_code=404, detail="Video file ID not found.")
    # Only SRT for MVP
    try:
        detect_subtitle_format(sub_path)
        estimated_offset = estimate_sync_offset(sub_path)
        synced = abs(estimated_offset) < 0.4
        return SyncCheckResponse(
            is_synced=synced,
            recommended_offset=0.0 if synced else estimated_offset,
            details="Heuristic check based on subtitle start time. Not actual A/V analysis."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# PUBLIC_INTERFACE
@app.post("/fix_sync", summary="Auto-correct subtitle sync", tags=["sync"], response_model=SyncFixResponse)
async def fix_sync(request: SyncFixRequest):
    """
    Apply offset (auto-detected or user-specified) to subtitle file for sync.
    """
    sub_path = storage_index.get(request.subtitle_file_id)
    if not sub_path or not os.path.exists(sub_path):
        raise HTTPException(status_code=404, detail="Subtitle file not found.")
    try:
        detect_subtitle_format(sub_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # For now, only .srt
    used_offset = request.offset
    if used_offset is None:
        used_offset = estimate_sync_offset(sub_path)
    # Generate new file
    corr_id = uuid.uuid4().hex
    output_path = os.path.join(WORKING_DIR, f"corr_{corr_id}.srt")
    num_changed = apply_srt_offset(sub_path, output_path, used_offset)
    storage_index[corr_id] = output_path
    return SyncFixResponse(
        corrected_subtitle_file_id=corr_id,
        used_offset=used_offset,
        message=f"Applied {used_offset:.2f} seconds adjustment to {num_changed} subtitle entries."
    )

# PUBLIC_INTERFACE
@app.get("/download", summary="Download file", tags=["sync"])
async def download_file(file_id: str):
    """
    Download a previously uploaded video/subtitle or corrected file.
    Provide ?file_id=... as query parameter.
    """
    file_path = storage_index.get(file_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        headers={"Cache-Control": "no-cache"}
    )

@app.get("/", summary="Health Check")
def health_check():
    """API health check."""
    return {"message": "Healthy"}

