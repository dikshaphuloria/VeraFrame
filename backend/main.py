from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from pathlib import Path
import os
import tempfile
import shutil
import json
import subprocess

from extractor import extract_frames, frame_to_base64
from analyzer import analyze_frame_with_gemini, analyze_transition_with_gemini
from scorer import build_verdict
from models import MAX_FILE_SIZE, ALLOWED_VIDEO_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS

load_dotenv()

app = FastAPI(title="VeraFrame API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "TrueFrame API is running"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "google_api_key_loaded": bool(os.getenv("GOOGLE_API_KEY"))
    }


# ─── Shared pipeline ───────────────────────────────────────────────────────────

async def _run_analysis_stream(frame_paths: list[str]):
    """
    Core streaming generator — analyzes frames + transitions
    and yields SSE progress events.
    Used by both /analyze-stream and /analyze-url-stream.
    """
    total_frames = len(frame_paths)
    total_steps = total_frames + (total_frames - 1)
    current_step = 0

    # step 1 — analyze each frame
    frame_results = []
    for i, path in enumerate(frame_paths):
        b64 = frame_to_base64(path)
        progress = 20 + int((current_step / total_steps) * 60)
        yield f"data: {json.dumps({'step': 'analyzing_frame', 'message': f'Analyzing frame {i + 1} of {total_frames}...', 'progress': progress})}\n\n"

        try:
            analysis = analyze_frame_with_gemini(b64)
        except Exception as e:
            analysis = {
                "is_ai_generated": False,
                "confidence": 0,
                "artifacts_found": [],
                "reasoning": f"Could not analyze frame: {str(e)}"
            }

        frame_results.append({
            "filename": os.path.basename(path),
            "image": b64,
            "analysis": analysis
        })
        current_step += 1

    # step 2 — analyze transitions between consecutive frames
    transition_results = []
    for i in range(len(frame_results) - 1):
        progress = 20 + int((current_step / total_steps) * 60)
        yield f"data: {json.dumps({'step': 'analyzing_transition', 'message': f'Analyzing transition {i + 1} of {total_frames - 1}...', 'progress': progress})}\n\n"

        try:
            transition = analyze_transition_with_gemini(
                frame_results[i]["image"],
                frame_results[i + 1]["image"],
                i + 1
            )
        except Exception as e:
            transition = {
                "is_suspicious_transition": False,
                "confidence": 0,
                "transition_type": "normal",
                "description": f"Could not analyze: {str(e)}",
                "frame_pair": f"frame {i + 1} → frame {i + 2}"
            }

        transition_results.append(transition)
        current_step += 1

    # step 3 — build final verdict
    yield f"data: {json.dumps({'step': 'verdict', 'message': 'Building verdict...', 'progress': 90})}\n\n"

    result = build_verdict(frame_results, transition_results)

    yield f"data: {json.dumps({'step': 'complete', 'message': 'Analysis complete!', 'progress': 100, 'result': result})}\n\n"


# ─── Video file upload ─────────────────────────────────────────────────────────

@app.post("/analyze-stream")
async def analyze_stream(file: UploadFile = File(...)):
    """Upload a video file and stream analysis progress via SSE"""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 100MB")

    async def generate():
        with tempfile.TemporaryDirectory() as temp_dir:
            yield f"data: {json.dumps({'step': 'uploading', 'message': 'Saving video...', 'progress': 5})}\n\n"

            video_path = os.path.join(temp_dir, file.filename)
            with open(video_path, "wb") as f:
                f.write(contents)

            yield f"data: {json.dumps({'step': 'extracting', 'message': 'Extracting frames...', 'progress': 15})}\n\n"

            frames_dir = os.path.join(temp_dir, "frames")
            os.makedirs(frames_dir)

            try:
                frame_paths = extract_frames(video_path, frames_dir)
            except Exception as e:
                yield f"data: {json.dumps({'step': 'error', 'message': str(e), 'progress': 0})}\n\n"
                return

            if not frame_paths:
                yield f"data: {json.dumps({'step': 'error', 'message': 'No frames could be extracted', 'progress': 0})}\n\n"
                return

            async for event in _run_analysis_stream(frame_paths):
                yield event

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── YouTube / URL ─────────────────────────────────────────────────────────────

class URLRequest(BaseModel):
    url: str


@app.post("/analyze-url-stream")
async def analyze_url_stream(request: URLRequest):
    """Download a YouTube or direct video URL and stream analysis progress via SSE"""

    async def generate():
        with tempfile.TemporaryDirectory() as temp_dir:
            yield f"data: {json.dumps({'step': 'uploading', 'message': 'Downloading video...', 'progress': 5})}\n\n"

            video_path = os.path.join(temp_dir, "video.mp4")

            try:
                result = subprocess.run(
                    [
                        "yt-dlp",
                        "-f", "mp4",
                        "-o", video_path,
                        "--max-filesize", "100m",
                        "--match-filter", "duration < 600",
                        request.url
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    yield f"data: {json.dumps({'step': 'error', 'message': 'Could not download video. Make sure it is under 10 minutes and publicly accessible.', 'progress': 0})}\n\n"
                    return
            except subprocess.TimeoutExpired:
                yield f"data: {json.dumps({'step': 'error', 'message': 'Download timed out. Try a shorter video.', 'progress': 0})}\n\n"
                return

            yield f"data: {json.dumps({'step': 'extracting', 'message': 'Extracting frames...', 'progress': 15})}\n\n"

            frames_dir = os.path.join(temp_dir, "frames")
            os.makedirs(frames_dir)

            try:
                frame_paths = extract_frames(video_path, frames_dir)
            except Exception as e:
                yield f"data: {json.dumps({'step': 'error', 'message': str(e), 'progress': 0})}\n\n"
                return

            if not frame_paths:
                yield f"data: {json.dumps({'step': 'error', 'message': 'No frames could be extracted', 'progress': 0})}\n\n"
                return

            async for event in _run_analysis_stream(frame_paths):
                yield event

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    """Analyze a single image or screenshot for AI generation"""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

    with tempfile.TemporaryDirectory() as temp_dir:
        image_path = os.path.join(temp_dir, file.filename)
        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        b64 = frame_to_base64(image_path)

        try:
            analysis = analyze_frame_with_gemini(b64, image_path=image_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        frame = {"filename": file.filename, "image": b64, "analysis": analysis}

        # route through build_verdict so ELA + metadata are respected
        result = build_verdict([frame], [])
        return result