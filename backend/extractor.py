import os
import base64
import subprocess
import io
from pathlib import Path
from PIL import Image
from fastapi import HTTPException
from models import MAX_FRAMES  # Use relative import if models is in the same package


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe"""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 60  # fallback to 60s if ffprobe output is unparseable


def get_fps_for_duration(duration: float) -> float:
    """
    Pick extraction rate based on video duration
    so frames are spread evenly across the whole video
    - Under 30s  → 1 frame every 3s
    - 30s–2min  → 1 frame every 10s
    - Over 2min  → 1 frame every 20s
    """
    if duration <= 30:
        return 0.33
    elif duration <= 120:
        return 0.1
    else:
        return 0.05


def extract_frames(video_path: str, output_dir: str) -> list[str]:
    """
    Extract up to MAX_FRAMES frames from a video using FFmpeg.
    Frame rate adapts to video duration for even coverage.
    """
    duration = get_video_duration(video_path)
    fps = get_fps_for_duration(duration)

    print(f"Video duration: {duration:.1f}s → extracting at {fps} fps")

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    command = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        "-vframes", str(MAX_FRAMES),
        output_pattern,
        "-y"
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"FFmpeg error: {result.stderr}")

    frames = sorted(Path(output_dir).glob("frame_*.jpg"))
    return [str(f) for f in frames]


def frame_to_base64(frame_path: str, max_width: int = 512) -> str:
    """
    Convert a frame image to base64.
    Resizes to max_width to keep payload size small.
    """
    img = Image.open(frame_path)

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=60)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")