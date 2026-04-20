def normalize_artifact(s: str) -> str:
    """Lowercase and strip trailing punctuation for deduplication"""
    return s.lower().rstrip(".,;:").strip()


def dedupe_artifacts(all_artifacts: list[str]) -> list[str]:
    """Remove duplicate artifacts using normalized comparison"""
    seen = set()
    unique = []
    for a in all_artifacts:
        key = normalize_artifact(a)
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def build_verdict(frame_results: list[dict], transition_results: list[dict]) -> dict:
    """
    Combine per-frame, transition, ELA, and metadata analysis into a final verdict.

    Scoring weights:
    - Frame analysis:      40%
    - Transition analysis: 60% (harder to fake, catches modern AI)

    Four possible verdicts:
    - AI Generated        → strong AI signals in frames or transitions
    - Possibly AI Generated → weak AI signals
    - Possibly Edited     → visually real but ELA/metadata shows manipulation
    - Likely Real         → no AI or manipulation signals found
    """

    # ── Frame scores ──────────────────────────────────────────────────────────
    ai_scores = [
        f["analysis"]["confidence"]
        for f in frame_results
        if f["analysis"]["is_ai_generated"]
    ]
    real_scores = [
        f["analysis"]["confidence"]
        for f in frame_results
        if not f["analysis"]["is_ai_generated"]
    ]

    ai_frame_count = len(ai_scores)
    total_frames = len(frame_results)
    ai_frame_ratio = ai_frame_count / total_frames if total_frames > 0 else 0

    avg_ai_confidence = sum(ai_scores) / len(ai_scores) if ai_scores else 0
    avg_real_confidence = sum(real_scores) / len(real_scores) if real_scores else 0

    frame_score = avg_ai_confidence * (0.6 + 0.4 * ai_frame_ratio)

    # ── Transition scores ─────────────────────────────────────────────────────
    suspicious_transitions = [t for t in transition_results if t["is_suspicious_transition"]]
    suspicious_count = len(suspicious_transitions)
    total_transitions = len(transition_results)
    transition_ratio = suspicious_count / total_transitions if total_transitions > 0 else 0

    avg_transition_confidence = (
        sum(t["confidence"] for t in suspicious_transitions) / suspicious_count
        if suspicious_count > 0 else 0
    )
    transition_score = avg_transition_confidence * (0.6 + 0.4 * transition_ratio)

    # ── Combined raw score ────────────────────────────────────────────────────
    overall_confidence = round((frame_score * 0.4) + (transition_score * 0.6), 1)

    # ── ELA / Metadata signals ────────────────────────────────────────────────
    ela_edited_frames = [
        f for f in frame_results
        if f["analysis"].get("ela") and f["analysis"]["ela"].get("likely_edited")
    ]
    ela_heavily_edited_frames = [
        f for f in frame_results
        if f["analysis"].get("ela") and f["analysis"]["ela"].get("heavily_edited")
    ]
    metadata_edited_frames = [
        f for f in frame_results
        if f["analysis"].get("metadata") and f["analysis"]["metadata"].get("is_edited")
    ]

    has_metadata_signal = bool(metadata_edited_frames)

    # ── Verdict logic ─────────────────────────────────────────────────────────

    # strong AI transition signal
    if suspicious_count >= 2 and avg_transition_confidence >= 85:
        verdict = "AI Generated"

    elif suspicious_count >= 3 and avg_transition_confidence >= 70:
        verdict = "AI Generated"

    # no AI signals at all — check for editing
    elif ai_frame_count == 0 and suspicious_count == 0:

        if ela_heavily_edited_frames or metadata_edited_frames:
            # visually real but forensics say heavily edited
            verdict = "Possibly Edited"
            ela_scores = [
                f["analysis"]["ela"]["ela_score"]
                for f in ela_heavily_edited_frames
                if f["analysis"].get("ela")
            ]
            overall_confidence = round(
                max(
                    max(ela_scores) if ela_scores else 0,
                    70.0 if has_metadata_signal else 0
                ), 1
            )

        elif ela_edited_frames:
            # mild ELA signal — possible subtle edit
            verdict = "Possibly Edited"
            ela_scores = [
                f["analysis"]["ela"]["ela_score"]
                for f in ela_edited_frames
                if f["analysis"].get("ela")
            ]
            overall_confidence = round(max(ela_scores) if ela_scores else 40.0, 1)
            overall_confidence = max(overall_confidence, 40.0)

        elif avg_real_confidence >= 80:
            # clean — no AI, no editing signals
            verdict = "Likely Real"
            overall_confidence = round(avg_real_confidence, 1)

        else:
            # real frames but low confidence — be cautious
            verdict = "Possibly AI Generated"
            overall_confidence = round(50 + (50 * (1 - avg_real_confidence / 100)), 1)

    # weak AI frame signals
    elif ai_frame_count <= 2 and avg_ai_confidence < 60 and suspicious_count <= 1:
        verdict = "Possibly AI Generated"

    # everything else — strong AI signals
    else:
        verdict = "AI Generated"

    # ── Confidence must always match verdict ──────────────────────────────────
    if verdict == "AI Generated":
        overall_confidence = max(overall_confidence, 60.0)

    elif verdict == "Possibly AI Generated":
        overall_confidence = max(overall_confidence, 35.0)
        overall_confidence = min(overall_confidence, 69.9)

    elif verdict == "Possibly Edited":
        overall_confidence = max(overall_confidence, 40.0)
        overall_confidence = min(overall_confidence, 85.0)

    elif verdict == "Likely Real":
        overall_confidence = max(overall_confidence, 70.0)

    overall_confidence = round(overall_confidence, 1)

    # ── Collect and dedupe artifacts ──────────────────────────────────────────
    all_artifacts = []
    for f in frame_results:
        all_artifacts.extend(f["analysis"].get("artifacts_found", []))
    unique_artifacts = dedupe_artifacts(all_artifacts)

    # ── Sort frames most suspicious first ─────────────────────────────────────
    sorted_frames = sorted(
        frame_results,
        key=lambda f: f["analysis"]["confidence"] if f["analysis"]["is_ai_generated"] else 0,
        reverse=True
    )

    return {
        "verdict": verdict,
        "overall_confidence": overall_confidence,
        "ai_frames": ai_frame_count,
        "total_frames": total_frames,
        "artifacts_found": unique_artifacts,
        "proof_frames": sorted_frames[:4],
        "all_frames": sorted_frames,
        "transitions": {
            "total_analyzed": total_transitions,
            "suspicious_count": suspicious_count,
            "results": transition_results
        }
    }