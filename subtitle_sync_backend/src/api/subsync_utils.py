# Utilities for subtitle sync backend: handling subtitles, sync checks, and correction.

import os
import re

class SubtitleFormatError(Exception):
    pass

# PUBLIC_INTERFACE
def detect_subtitle_format(file_path: str) -> str:
    """
    Detects the subtitle format based on file extension or simple signature.
    Returns 'srt', 'vtt', etc., or raises SubtitleFormatError.
    """
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".srt":
        return "srt"
    if ext == ".vtt":
        return "vtt"
    with open(file_path, "r", encoding="utf-8") as f:
        firstline = f.readline().strip()
        if firstline.startswith("WEBVTT"):
            return "vtt"
        elif re.match(r"^\d+\s*$", firstline):
            return "srt"
    raise SubtitleFormatError("Unsupported subtitle format")

# PUBLIC_INTERFACE
def parse_srt(file_content: str):
    """
    Parses .srt subtitle content into list of (start, end, text) tuples.
    Times are in seconds.
    """
    entries = []
    blocks = file_content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        time_line = lines[1]
        match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
        if match:
            start = _srt_time_to_seconds(match.group(1))
            end = _srt_time_to_seconds(match.group(2))
            text = "\n".join(lines[2:])
            entries.append((start, end, text))
    return entries

def _srt_time_to_seconds(timestr: str) -> float:
    h, m, s_ms = timestr.split(":")
    s, ms = s_ms.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def _seconds_to_srt_time(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

# PUBLIC_INTERFACE
def serialize_srt(entries):
    """
    Serialize a list of (start, end, text) tuples as SRT file content.
    """
    out = []
    for i, (start, end, text) in enumerate(entries, 1):
        out.append(str(i))
        out.append(f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}")
        out.append(text)
        out.append("")
    return "\n".join(out)

# PUBLIC_INTERFACE
def check_subtitle_sync(video_path: str, subtitle_path: str):
    """
    Dummy sync check for demo: just checks if subtitles start after 0s.
    Returns offset in seconds needed to align (negative=starts too early).
    In real-world case, use audio/speech/ASR features, here only naive check.
    """
    # Read first subtitle start time
    with open(subtitle_path, "r", encoding="utf-8") as f:
        fmt = detect_subtitle_format(subtitle_path)
        if fmt == "srt":
            entries = parse_srt(f.read())
        else:
            raise SubtitleFormatError("Format not supported yet")
    if not entries:
        return 0.0
    first_start = entries[0][0]
    # Naive: if first subtitle starts after 1 second, suggest negative offset
    # else, return 0.
    if first_start > 1.0:
        return -first_start  # Should shift subtitles earlier to match video
    return 0.0

# PUBLIC_INTERFACE
def apply_sync_correction(subtitle_path: str, offset_sec: float, output_path: str):
    """
    Apply offset (in seconds) to all subtitles and save to new file.
    Supports only SRT for demo.
    """
    with open(subtitle_path, "r", encoding="utf-8") as f:
        fmt = detect_subtitle_format(subtitle_path)
        if fmt == "srt":
            entries = parse_srt(f.read())
            new_entries = [(max(0, start + offset_sec), max(0, end + offset_sec), text) for start, end, text in entries]
            with open(output_path, "w", encoding="utf-8") as fw:
                fw.write(serialize_srt(new_entries))
            return output_path
        else:
            raise SubtitleFormatError("Format not supported yet")
