from models import MAX_FRAMES

# ─── Constants ─────────────────────────────────────────────────────────────────
MAX_PROOF_FRAMES = 4   # how many frames to surface in the result as "proof"

# ELA thresholds — scorer owns all threshold decisions, not analyzer.py
_ELA_LIKELY_EDITED_THRESHOLD  = 25
_ELA_HEAVILY_EDITED_THRESHOLD = 55


# ─── Artifact deduplication ────────────────────────────────────────────────────

def normalize_artifact(s: str) -> str:
    """Lowercase and strip trailing punctuation for deduplication."""
    return s.lower().rstrip(".,;:").strip()


def dedupe_artifacts(all_artifacts: list[str]) -> list[str]:
    """Remove duplicate artifacts using normalized comparison."""
    seen = set()
    unique = []
    for a in all_artifacts:
        key = normalize_artifact(a)
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# ─── Main scoring pipeline ─────────────────────────────────────────────────────

def build_verdict(frame_results: list[dict], transition_results: list[dict]) -> dict:
    """
    Scoring pipeline — four signals feed into one final verdict.

    SIGNAL 1 — Frame score      (what individual frames look like, Gemini vision)
    SIGNAL 2 — Transition score (physics consistency between consecutive frames)
    SIGNAL 3 — ELA score        (pixel-level manipulation detection)
    SIGNAL 4 — Metadata score   (editing software detected in EXIF)

    Signals 3 and 4 only affect the "Possibly Edited" verdict branch.
    They do NOT feed into AI generation scoring — editing ≠ AI generation.

    Four verdicts:
    - AI Generated          → strong AI signals in frames or transitions
    - Possibly AI Generated → some AI signals but uncertain
    - Possibly Edited       → visually real but forensics detect manipulation
    - Likely Real           → no AI or manipulation signals found

    Confidence floors and ceilings per verdict:
    - AI Generated:          60% – 100%
    - Possibly AI Generated: 35% – 69.9%
    - Possibly Edited:       30% – 85%
    - Likely Real:           55% – 100%   (was 70%, lowered for honesty when evidence is thin)
    """

    total_frames      = len(frame_results)
    total_transitions = len(transition_results)

    # ── SIGNAL 1: Frame analysis ───────────────────────────────────────────────
    # Spread AI confidence across ALL frames so a single suspicious frame out of
    # many doesn't dominate the verdict.
    # Example: 1 AI frame at 95% out of 5 total → avg_ai_confidence = 95/5 = 19

    ai_scores   = [
        f["analysis"]["confidence"]
        for f in frame_results
        if f["analysis"].get("is_ai_generated")
    ]
    real_scores = [
        f["analysis"]["confidence"]
        for f in frame_results
        if not f["analysis"].get("is_ai_generated")
    ]

    ai_frame_count = len(ai_scores)
    ai_ratio       = ai_frame_count / total_frames if total_frames > 0 else 0

    # spread across total — prevents minority AI frames dominating verdict
    avg_ai_confidence = sum(ai_scores) / total_frames if total_frames > 0 else 0

    # per-group averages — used for confidence display and verdict thresholds
    avg_ai_per_frame   = sum(ai_scores)   / ai_frame_count   if ai_frame_count > 0 else 0
    avg_real_per_frame = sum(real_scores) / len(real_scores) if real_scores      else 0

    frame_signal = avg_ai_confidence  # 0-100, higher = more AI evidence

    # ── SIGNAL 2: Transition analysis ─────────────────────────────────────────
    # Spread suspicious confidence across ALL transitions.
    # Example: 1 suspicious out of 5 transitions → transition_signal ≈ 19, not 95.

    suspicious_transitions    = [t for t in transition_results if t.get("is_suspicious_transition")]
    suspicious_count          = len(suspicious_transitions)
    avg_transition_confidence = (
        sum(t["confidence"] for t in suspicious_transitions) / suspicious_count
        if suspicious_count > 0 else 0
    )
    transition_signal = (
        sum(t["confidence"] for t in suspicious_transitions) / total_transitions
        if total_transitions > 0 else 0
    )

    # ── SIGNAL 3: ELA ─────────────────────────────────────────────────────────
    # Read raw ELA scores from analyzer; apply thresholds here.
    # Note: ELA only runs on original uploaded images, not video frames.
    # For video, ela_scores will be empty and ela_signal = 0.

    ela_scores = [
        f["analysis"]["ela"]["ela_score"]
        for f in frame_results
        if f["analysis"].get("ela")
    ]
    ela_signal         = max(ela_scores) if ela_scores else 0
    ela_likely_edited  = ela_signal > _ELA_LIKELY_EDITED_THRESHOLD
    ela_heavily_edited = ela_signal > _ELA_HEAVILY_EDITED_THRESHOLD

    # ── SIGNAL 4: Metadata ────────────────────────────────────────────────────
    # is_edited comes from analyzer.py's forensic check (ELA + metadata combined).
    # We also check metadata directly for software detection in artifact descriptions.

    metadata_edited = any(
        (f["analysis"].get("metadata") or {}).get("is_edited")
        for f in frame_results
    )
    metadata_signal = 80 if metadata_edited else 0

    forensic_manipulation = ela_likely_edited or metadata_edited

    # ── ARTIFACTS ─────────────────────────────────────────────────────────────
    # Collect Gemini-reported artifacts from all frames.
    # Forensic artifact descriptions were already added by analyzer.py;
    # we add any scorer-level context here and deduplicate at the end.

    all_artifacts = []
    for f in frame_results:
        all_artifacts.extend(f["analysis"].get("artifacts_found", []))

    # add metadata software description at scorer level if not already present
    if metadata_edited:
        software = next(
            (
                f["analysis"]["metadata"]["software_detected"]
                for f in frame_results
                if (f["analysis"].get("metadata") or {}).get("is_edited")
            ),
            "unknown"
        )
        all_artifacts.append(f"Editing software detected in metadata: {software}")

    # add ELA description at scorer level with threshold context
    if ela_heavily_edited:
        all_artifacts.append(
            f"Strong manipulation detected via ELA (score: {ela_signal}) — significant editing likely"
        )
    elif ela_likely_edited:
        all_artifacts.append(
            f"Mild ELA signal detected (score: {ela_signal}) — possible subtle filtering or recompression"
        )

    if any(
        (f["analysis"].get("metadata") or {}).get("no_metadata") and
        not (f["analysis"].get("metadata") or {}).get("has_camera_metadata")
        for f in frame_results
        if f["analysis"].get("metadata")
    ):
        all_artifacts.append(
            "No camera metadata found — image may have been generated or stripped"
        )

    unique_artifacts = dedupe_artifacts(all_artifacts)

    # ── VERDICT + RAW SCORE ────────────────────────────────────────────────────
    # Pattern-based verdict first, then raw_score set to reflect actual evidence.
    # Confidence shown to user is derived from raw_score after floors/ceilings.

    # CASE 1: Strong AI transition signal — most reliable AI indicator
    if suspicious_count >= 2 and avg_transition_confidence >= 85:
        verdict   = "AI Generated"
        raw_score = avg_transition_confidence

    # CASE 2: Majority of frames are high-confidence AI
    elif ai_ratio >= 0.5 and avg_ai_per_frame >= 70:
        verdict   = "AI Generated"
        raw_score = avg_ai_per_frame

    # CASE 3: Some AI frames or a meaningful transition signal.
    # raw_score: use the larger of the two signals, clamped to 100.
    # Previously used frame_signal * 2 which could exceed 100 before clamping.
    elif ai_ratio >= 0.2 or (suspicious_count >= 1 and avg_transition_confidence >= 60):
        verdict   = "Possibly AI Generated"
        raw_score = min(max(frame_signal, transition_signal), 100)

    # CASE 4: No AI signals at all — check forensics
    elif ai_frame_count == 0 and suspicious_count == 0:

        if ela_heavily_edited or metadata_edited:
            verdict   = "Possibly Edited"
            raw_score = max(ela_signal, metadata_signal)

        elif ela_likely_edited:
            verdict   = "Possibly Edited"
            raw_score = ela_signal

        else:
            verdict   = "Likely Real"
            raw_score = avg_real_per_frame

    # CASE 5: Weak AI signals but forensic evidence present — editing wins
    elif forensic_manipulation:
        verdict   = "Possibly Edited"
        raw_score = max(ela_signal, metadata_signal)

    # CASE 6: Catch-all — weak unclassified AI signals
    else:
        verdict   = "Possibly AI Generated"
        raw_score = frame_signal

    # ── CONFIDENCE FLOORS AND CEILINGS ────────────────────────────────────────
    # Confidence must never contradict the verdict label.
    #
    # AI Generated:          60% – 100%   (strong positive signal required)
    # Possibly AI Generated: 35% – 69.9%  (uncertain, not strong enough to confirm)
    # Possibly Edited:       30% – 85%    (forensic, not AI certainty)
    # Likely Real:           55% – 100%   (floor lowered from 70 — honest when thin evidence)

    overall_confidence = round(raw_score, 1)

    if verdict == "AI Generated":
        overall_confidence = max(overall_confidence, 60.0)

    elif verdict == "Possibly AI Generated":
        overall_confidence = max(overall_confidence, 35.0)
        overall_confidence = min(overall_confidence, 69.9)

    elif verdict == "Possibly Edited":
        overall_confidence = max(overall_confidence, 30.0)
        overall_confidence = min(overall_confidence, 85.0)

    elif verdict == "Likely Real":
        overall_confidence = max(overall_confidence, 55.0)  # was 70, lowered for honesty

    overall_confidence = round(overall_confidence, 1)

    # ── SORT FRAMES — most suspicious first ───────────────────────────────────
    sorted_frames = sorted(
        frame_results,
        key=lambda f: f["analysis"]["confidence"] if f["analysis"].get("is_ai_generated") else 0,
        reverse=True
    )

    return {
        "verdict": verdict,
        "overall_confidence": overall_confidence,
        "ai_frames": ai_frame_count,
        "total_frames": total_frames,
        "artifacts_found": unique_artifacts,
        "proof_frames": sorted_frames[:MAX_PROOF_FRAMES],
        "all_frames": sorted_frames,
        "transitions": {
            "total_analyzed": total_transitions,
            "suspicious_count": suspicious_count,
            "results": transition_results
        }
    }