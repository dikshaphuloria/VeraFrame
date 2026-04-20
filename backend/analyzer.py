import re
import base64
import json
import os
import io
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def clean_json_response(raw_text: str) -> dict:
    """
    Robustly extract JSON from Gemini response.
    Handles cases where the model adds conversational filler or markdown.
    """
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in Gemini response: {raw_text[:200]}")


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

        # no exif at all is suspicious for a "real" photo
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

    Returns a score 0-100 where higher = more likely edited/manipulated
    """
    try:
        original = Image.open(image_path).convert("RGB")

        # re-save at known quality level
        buffer = io.BytesIO()
        original.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        recompressed = Image.open(buffer).convert("RGB")

        # pixel-by-pixel difference
        diff = ImageChops.difference(original, recompressed)

        # amplify the differences so they're measurable
        enhanced = ImageEnhance.Brightness(diff).enhance(10)

        # convert to numpy array for math
        diff_array = np.array(enhanced, dtype=np.float32)

        # overall average brightness of diff
        mean_ela = float(diff_array.mean())

        # standard deviation — high std = inconsistent editing (suspicious)
        std_ela = float(diff_array.std())

        # max brightness — very bright spots = heavily edited regions
        max_ela = float(diff_array.max())

        # normalize to 0-100 score
        # empirically: untouched images score ~5-15, edited ~25-60, heavy edits 60+
        ela_score = min(round(mean_ela * 1.5 + std_ela * 0.5, 1), 100)

        return {
            "ela_score": ela_score,
            "mean": round(mean_ela, 2),
            "std": round(std_ela, 2),
            "max": round(max_ela, 2),
            "likely_edited": ela_score > 20,
            "heavily_edited": ela_score > 40,
        }
    except Exception as e:
        return {
            "ela_score": 0,
            "mean": 0,
            "std": 0,
            "max": 0,
            "likely_edited": False,
            "heavily_edited": False,
            "error": str(e)
        }


def analyze_frame_with_gemini(image_data: str, image_path: str = None) -> dict:
    """
    Send a single frame to Gemini Vision.
    Also runs metadata + ELA checks if image_path provided.
    Returns combined per-frame AI detection verdict.
    """
    image_bytes = base64.b64decode(image_data)
    image = Image.open(io.BytesIO(image_bytes))

    # run metadata + ELA if we have the original file path
    metadata = None
    ela = None
    if image_path:
        metadata = check_image_metadata(image_path)
        ela = error_level_analysis(image_path)

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

    GOLDEN RULE:
    Ask yourself — could this scene exist in real life and be filmed by a normal person?
    If YES and the only issues are video quality → mark as REAL
    If there is something PHYSICALLY IMPOSSIBLE regardless of quality → mark as AI

    Respond ONLY with a JSON object in this exact format, no extra text:
    {
        "is_ai_generated": true or false,
        "confidence": a number between 0 and 100,
        "watermark_detected": false,
        "artifacts_found": ["only list genuinely AI-specific artifacts, not video quality issues"],
        "reasoning": "one sentence citing the strongest AI-specific signal, or why it appears real"
    }
    """

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[prompt, image]
    )

    result = clean_json_response(response.text)

    # inject metadata + ELA findings into result
    if metadata or ela:
        result["metadata"] = metadata
        result["ela"] = ela

        extra_artifacts = []

        # if photoshop/editing software detected in metadata
        if metadata and metadata["is_edited"] and metadata["software_detected"]:
            extra_artifacts.append(f"Editing software detected in metadata: {metadata['software_detected']}")
            # boost confidence if editing software found
            result["confidence"] = min(result["confidence"] + 20, 100)

        # if ELA shows heavy manipulation
        if ela and ela["heavily_edited"]:
            extra_artifacts.append(f"Heavy image manipulation detected via ELA (score: {ela['ela_score']})")
            result["confidence"] = min(result["confidence"] + 15, 100)
        elif ela and ela["likely_edited"]:
            extra_artifacts.append(f"Possible image manipulation detected via ELA (score: {ela['ela_score']})")
            result["confidence"] = min(result["confidence"] + 8, 100)

        # if no camera metadata at all — mildly suspicious
        if metadata and metadata["no_metadata"] and not metadata["has_camera_metadata"]:
            extra_artifacts.append("No camera metadata found — image may have been generated or stripped")

        if extra_artifacts:
            result["artifacts_found"].extend(extra_artifacts)
            # if we found editing evidence, upgrade verdict if it was real
            if not result["is_ai_generated"] and (
                (metadata and metadata["is_edited"]) or
                (ela and ela["heavily_edited"])
            ):
                result["is_ai_generated"] = True
                result["reasoning"] = "Forensic analysis detected image manipulation even though visual content appears authentic"

    return result


def analyze_transition_with_gemini(frame1_data: str, frame2_data: str, frame_num: int) -> dict:
    """
    Send two consecutive frames to Gemini.
    Detects physically impossible transitions that reveal AI generation.
    Focuses on object permanence, fluid dynamics, and physics consistency.
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

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[prompt, image1, image2]
    )

    result = clean_json_response(response.text)
    result["frame_pair"] = f"frame {frame_num} → frame {frame_num + 1}"
    return result