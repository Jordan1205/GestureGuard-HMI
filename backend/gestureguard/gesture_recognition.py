"""Image-space geometric checks; no depth or calibrated-probability claims."""
from math import hypot, isfinite
from typing import Sequence

HAND_CONNECTIONS = ((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
                    (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),
                    (15,16),(13,17),(0,17),(17,18),(18,19),(19,20))


def pinch_geometry(points: Sequence[Sequence[float]], aspect: float = 4/3) -> tuple[float, float]:
    """Return tip/palm ratio and palm width relative to frame width.

    Normalized x/y have different pixel scales; y is divided by width/height.
    Palm width normalizes distance, reducing sensitivity to camera distance.
    z is deliberately unused. Degenerate or missing geometry fails closed.
    """
    if len(points) != 21 or not isfinite(aspect) or aspect <= 0 or any(len(p) < 2 or not isfinite(p[0]) or not isfinite(p[1]) for p in points):
        return float("inf"), 0.0
    def distance(a: int, b: int) -> float:
        return hypot(points[a][0]-points[b][0], (points[a][1]-points[b][1])/aspect)
    palm = distance(5, 17)
    if palm < 1e-5:
        return float("inf"), 0.0
    return distance(4, 8)/palm, palm


def pinch_eligible(points: Sequence[Sequence[float]], aspect: float = 4/3) -> bool:
    """Reject fingertip overlap inside a curled fist using image-space geometry.

    The index tip must lie farther from the wrist than its MCP and point past
    the PIP joint. This is a conservative heuristic, not a physical angle model.
    """
    ratio, palm = pinch_geometry(points, aspect)
    if not isfinite(ratio) or palm <= 0:
        return False
    def distance(a: int, b: int) -> float:
        return hypot(points[a][0] - points[b][0], (points[a][1] - points[b][1]) / aspect)
    wrist_mcp, wrist_tip = distance(0, 5), distance(0, 8)
    wrist_pip = distance(0, 6)
    return wrist_tip >= max(wrist_mcp * 1.1, palm * .60) and wrist_tip >= wrist_pip * 1.03


def interpret_result(result, timestamp: float, elapsed_ms: float, settings, aspect: float = 4/3):
    """Convert MediaPipe Tasks output to hardware-independent Observation."""
    from .domain import Observation
    landmarks = [[[p.x, p.y, p.z] for p in hand] for hand in result.hand_landmarks]
    hands = len(landmarks)
    if not hands:
        return Observation(timestamp, source="live", recognition_ms=elapsed_ms), landmarks
    categories = sorted(result.gestures[0], key=lambda c: c.score, reverse=True) if result.gestures else []
    gesture = categories[0].category_name if categories else "None"
    score = float(categories[0].score) if categories else 0.0
    ambiguous = len(categories) > 1 and score - categories[1].score < .12
    ratio, scale = pinch_geometry(landmarks[0], aspect)
    eligible = pinch_eligible(landmarks[0], aspect) and not (gesture == "Closed_Fist" and score >= settings.threshold_for("Closed_Fist"))
    metadata = {"pinch_ratio": ratio if isfinite(ratio) else None,
                "pinch_eligible": eligible, "raw_canned_gesture": gesture,
                "raw_canned_score": score, "score_kind": "classifier_output"}
    if ratio <= settings.pinch_ratio and eligible and hands == 1:
        gesture = "Pinch"
        # This is a deterministic geometry quality index, not a learned confidence.
        score = max(0.0, min(1.0, 1.0 - ratio / settings.pinch_ratio))
        ambiguous = False
        metadata["score_kind"] = "geometric_quality_index"
    return Observation(timestamp, gesture, score, hands, ambiguous, "live", elapsed_ms,
                       hand_scale=scale, metadata=metadata), landmarks
