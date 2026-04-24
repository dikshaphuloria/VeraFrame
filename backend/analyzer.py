import re
import base64
import json
import os
import io
import time
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# ─── Gemini call defaults ──────────────────────────────────────────────────────
_GEMINI_MODEL        = "gemini-3-flash-preview"
_MAX_RETRIES         = 3
_RETRY_BASE_DELAY    = 2.0   # seconds — doubles each retry


# ─── Neutral fallback dicts ────────────────────────────────────────────────────
# Returned when Gemini fails after all retries so the pipeline keeps running.

def _neutral_frame_result() -> dict:
    return {
        "is_ai_generated": False,
        "is_edited": False,
        "confidence": 0,
        "watermark_detected": False,
        "artifacts_found": [],
        "reasoning": "Analysis failed — treated as real to avoid false positives",
        "metadata": None,
        "ela": None,
    }


def _neutral_transition_result(frame_num: int) -> dict:
    return {
        "is_suspicious_transition": False,
        "confidence": 0,
        "transition_type": "normal",
        "description": "Analysis failed — treated as normal transition",
        "frame_pair": f"frame {frame_num} → frame {frame_num + 1}",
    }


# ─── Helpers ───────────────────────────────────────────────────────────────────

def clean_json_response(raw_text: str) -> dict:
    """
    Robustly extract JSON from Gemini response.
    Handles cases where the model adds conversational filler or markdown.
    """
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in Gemini response: {raw_text[:200]}")


def _call_gemini_with_retry(contents: list) -> str:
    """
    Call Gemini with exponential backoff retry.
    Returns raw response text.
    Raises RuntimeError after all retries exhausted.
    """
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=_GEMINI_MODEL,
                contents=contents
            )
            return response.text
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
    raise RuntimeError(f"Gemini call failed after {_MAX_RETRIES} attempts: {last_error}")


# ─── Forensic helpers ──────────────────────────────────────────────────────────

def check_image_metadata(image_path: str) -> dict:
    """
    Check EXIF metadata for signs of editing software or missing camera data.
    Real photos taken on phones/cameras have rich metadata.
    AI generated or heavily edited images often have stripped or suspicious metadata.
    """
    try:
        img = Image.open(image_path)
        exif_data = img._getexif() if hasattr(img, "_getexif") else None

        suspicious_software = [
            "photoshop", "lightroom", "gimp", "midjourney",
            "stable diffusion", "dall-e", "firefly", "canva",
            "adobe", "snapseed", "facetune", "meitu"
        ]

        software = ""
        has_camera_make = False
        has_gps = False

        if exif_data:
            # tag 305 = Software
            # tag 271 = Camera Make (e.g. Apple, Samsung)
            # tag 272 = Camera Model
            # tag 34853 = GPS Info
            software = str(exif_data.get(305, "")).lower()
            has_camera_make = bool(exif_data.get(271) or exif_data.get(272))
            has_gps = bool(exif_data.get(34853))

        is_edited = any(s in software for s in suspicious_software)
        no_metadata = exif_data is None or len(exif_data) == 0

        return {
            "software_detected": software if software else None,
            "is_edited": is_edited,
            "has_camera_metadata": has_camera_make,
            "has_gps": has_gps,
            "no_metadata": no_metadata,
            "suspicion_score": (
                40 if is_edited else
                20 if no_metadata and not has_camera_make else
                0
            )
        }
    except Exception as e:
        return {
            "software_detected": None,
            "is_edited": False,
            "has_camera_metadata": False,
            "has_gps": False,
            "no_metadata": True,
            "suspicion_score": 0,
            "error": str(e)
        }


def error_level_analysis(image_path: str, quality: int = 90) -> dict:
    """
    ELA (Error Level Analysis) — detects image manipulation.

    How it works:
    1. Re-save the image at a known JPEG quality
    2. Compare original vs re-saved pixel by pixel
    3. Edited regions have DIFFERENT compression levels than the original
       so they show up as brighter/different in the diff image
    4. A uniform diff = untouched original
       A patchy diff with bright spots = edited regions

    NOTE: Only meaningful on the original uploaded file, not re-encoded
    video frames. Caller is responsible for only passing original image paths.

    Returns a score 0-100 where higher = more likely edited/manipulated.
    Thresholds are owned by scorer.py — this function returns raw values only.
    """
    try:
        original = Image.open(image_path).convert("RGB")

        buffer = io.BytesIO()
        original.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        recompressed = Image.open(buffer).convert("RGB")

        diff = ImageChops.difference(original, recompressed)
        enhanced = ImageEnhance.Brightness(diff).enhance(10)
        diff_array = np.array(enhanced, dtype=np.float32)

        mean_ela = float(diff_array.mean())
        std_ela  = float(diff_array.std())
        max_ela  = float(diff_array.max())

        # raw score — scorer.py owns the thresholds for "likely_edited" etc.
        ela_score = min(round(mean_ela * 1.5 + std_ela * 0.5, 1), 100)

        return {
            "ela_score": ela_score,
            "mean": round(mean_ela, 2),
            "std": round(std_ela, 2),
            "max": round(max_ela, 2),
        }
    except Exception as e:
        return {
            "ela_score": 0,
            "mean": 0,
            "std": 0,
            "max": 0,
            "error": str(e)
        }


# ─── Per-frame analysis ────────────────────────────────────────────────────────

def analyze_frame_with_gemini(image_data: str, image_path: str = None) -> dict:
    """
    Analyze a single frame for AI generation signals.

    Returns a dict with two independent verdicts:
      - is_ai_generated: Gemini vision detected AI generation artifacts
      - is_edited:       forensic analysis (ELA / metadata) detected manipulation

    These are intentionally separate. Editing ≠ AI generation.
    scorer.py maps these to the correct verdict tier.

    image_path should only be passed for original uploaded images, NOT for
    re-encoded video frames (ELA on re-encoded frames produces meaningless scores).
    """
    image_bytes = base64.b64decode(image_data)
    image = Image.open(io.BytesIO(image_bytes))

    # ── Forensic checks on original file (images only, not video frames) ───────
    metadata = None
    ela = None
    if image_path:
        metadata = check_image_metadata(image_path)
        ela = error_level_analysis(image_path)

    # ── Gemini vision analysis ─────────────────────────────────────────────────
    prompt = """
    You are an expert forensic analyst specializing in detecting AI-generated content.
    Analyze this image with EXTREME scrutiny BUT avoid false positives.

    VISUAL ARTIFACTS THAT SUGGEST AI:
    - Skin texture that is too smooth, waxy, or unnaturally perfect — NOT just low resolution
    - Hands or fingers that are deformed, fused, or have joints bending unnaturally
    - Hair that looks too perfect, lacks flyaways, or blends into background
    - Eyes that are too symmetrical, glassy, or have unnatural catch lights
    - Shadows pointing in different directions from impossible light sources
    - Edges of objects that look soft or melted in an AI-specific way — NOT motion blur
    - Gibberish text that mimics letters but has no meaning — NOT just blurry text
    - Fabric patterns that crawl, morph, or repeat unnaturally across the garment
    - Scenes that look too clean, too perfectly composed, too aesthetically pleasing
    - Objects that are physically impossible or defy gravity with no explanation

    SEMANTIC AND PHYSICS ERRORS THAT SUGGEST AI:
    - Impossible anatomy — joints bending in ways that defy skeletal structure
    - Reflections in mirrors or water that don't match the scene
    - Shadows that don't match the position of objects casting them
    - Objects floating with no physical support in a static scene

    THINGS THAT ARE NOT AI INDICATORS — DO NOT FLAG THESE:
    - Low resolution, pixelation, or compression artifacts — normal in phone/CCTV videos
    - Motion blur on fast moving objects — completely normal in real videos
    - Steam, smoke, or out of focus objects — not the same as floating objects
    - Messy, cluttered, dirty, or chaotic environments — MORE likely real than AI
    - Street food stalls, markets, kitchens, warehouses — almost never AI generated
    - Low budget or amateur video quality — not an AI signal
    - Grainy or noisy footage — real cameras produce sensor noise
    - Dark or unevenly lit scenes — normal in real environments

    MANIPULATION AND EDITING SIGNALS:
    - Areas that look unnaturally sharp or smooth compared to surrounding regions
    — suggests a patch or clone was applied
    - Halos or soft glowing edges around objects or people
    — classic sign of cut-and-paste compositing
    - Noise inconsistency — one region is grainy while adjacent region is
    unnaturally clean — suggests two images merged together
    - Color that doesn't match the ambient light — object looks like it was
    photographed in different lighting and dropped into the scene
    - Shadows missing under objects that should cast them
    - Repeated textures — identical patterns in background (clone stamp)
    - Over-sharpened edges on one subject while background is naturally soft

    GOLDEN RULE:
    Ask yourself — could this scene exist in real life and be filmed by a normal person?
    If YES and the only issues are video quality → mark as NOT AI generated
    If there is something PHYSICALLY IMPOSSIBLE regardless of quality → mark as AI generated

    Respond ONLY with a JSON object in this exact format, no extra text:
    {
        "is_ai_generated": true or false,
        "confidence": a number between 0 and 100,
        "watermark_detected": false,
        "artifacts_found": ["only list genuinely AI-specific artifacts, not video quality issues"],
        "reasoning": "one sentence citing the strongest AI-specific signal, or why it appears real"
    }
    """

    try:
        raw = _call_gemini_with_retry([prompt, image])
        result = clean_json_response(raw)
    except Exception:
        result = _neutral_frame_result()
        result["metadata"] = metadata
        result["ela"] = ela
        return result

    # ── Inject forensic signals as separate flags — do NOT touch is_ai_generated ──
    # Editing evidence goes into is_edited + artifacts_found only.
    # scorer.py decides how to weight editing vs AI generation in the final verdict.

    is_edited = False
    editing_artifacts = []

    if metadata:
        if metadata["is_edited"] and metadata["software_detected"]:
            is_edited = True
            editing_artifacts.append(
                f"Editing software detected in metadata: {metadata['software_detected']}"
            )
        if metadata["no_metadata"] and not metadata["has_camera_metadata"]:
            editing_artifacts.append(
                "No camera metadata found — image may have been generated or stripped"
            )

    if ela:
        ela_score = ela["ela_score"]
        # raw score passed to scorer; description added for artifact list
        if ela_score > 55:
            is_edited = True
            editing_artifacts.append(
                f"Heavy image manipulation detected via ELA (score: {ela_score})"
            )
        elif ela_score > 25:
            is_edited = True
            editing_artifacts.append(
                f"Possible image manipulation detected via ELA (score: {ela_score})"
            )

    result["is_edited"]       = is_edited
    result["metadata"]        = metadata
    result["ela"]             = ela
    result["artifacts_found"] = result.get("artifacts_found", []) + editing_artifacts

    return result


# ─── Transition analysis ───────────────────────────────────────────────────────

def analyze_transition_with_gemini(frame1_data: str, frame2_data: str, frame_num: int) -> dict:
    """
    Analyze two consecutive frames for physically impossible transitions
    that reveal AI generation. Focuses on object permanence, fluid dynamics,
    and physics consistency within a continuous shot.
    """
    image1 = Image.open(io.BytesIO(base64.b64decode(frame1_data)))
    image2 = Image.open(io.BytesIO(base64.b64decode(frame2_data)))

    prompt = """
    You are analyzing TWO CONSECUTIVE FRAMES from a video to detect AI generation.
    Image 1 is the EARLIER frame, Image 2 is the LATER frame.

    Your job is to find PHYSICALLY IMPOSSIBLE transitions — NOT normal video edits.

    NORMAL EDITING — mark as NOT suspicious:
    - Clean cut to a completely different scene, person, or location
    - Different people appearing in different clips compiled together
    - Indoor to outdoor, day to night, before to after
    - Different camera angles of the same event
    - Text overlays, titles, or captions changing
    - Zoom cuts or jump cuts within the same scene
    - Compilations where multiple unrelated clips are joined

    AI ARTIFACTS — mark as suspicious ONLY if in ONE CONTINUOUS SHOT:
    - Same person but animals or objects materialize around them impossibly
    - Objects teleport, multiply, or disappear with no edit
    - A person's face or clothing morphs mid-sentence
    - Background warps or ripples while subject stays still
    - Object permanence fails — person walks behind a pole and emerges as different person
    - Fluid dynamics break — water splashes that defy gravity or physics
    - Reflections in mirrors or water don't move in sync with the object
    - Fabric pattern on clothing crawls or shifts independently of movement
    - Person moves their hand but shirt fabric doesn't react to the movement
    - Same scene but lighting source changes direction impossibly fast

    THE KEY TEST:
    Could this be explained by a normal video edit or cut?
    If YES — NOT suspicious
    If NO — physics broke in a single continuous shot — suspicious

    CRITICAL: When in doubt, mark as NOT suspicious.
    False positives destroy user trust more than false negatives.

    Respond ONLY with this exact JSON, no extra text:
    {
        "is_suspicious_transition": true or false,
        "confidence": a number between 0 and 100,
        "transition_type": "one of: impossible_scene_change, physical_inconsistency, object_permanence_failure, fluid_dynamics_error, normal",
        "description": "one sentence — explain the specific physical impossibility or why it is a normal cut"
    }
    """

    try:
        raw = _call_gemini_with_retry([prompt, image1, image2])
        result = clean_json_response(raw)
    except Exception:
        return _neutral_transition_result(frame_num)

    result["frame_pair"] = f"frame {frame_num} → frame {frame_num + 1}"
    return result