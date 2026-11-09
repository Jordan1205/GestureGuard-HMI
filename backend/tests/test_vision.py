"""Geometry tests use synthetic landmarks, never claim real camera accuracy."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from gestureguard.domain import Settings
from gestureguard.gesture_recognition import interpret_result, pinch_eligible, pinch_geometry
from gestureguard.vision import VisionService


def hand(pinch_ratio=.2):
    points = [[.5, .5, 0] for _ in range(21)]
    points[5] = [.4, .5, 0]
    points[17] = [.6, .5, 0]
    points[4] = [.4, .3, 0]
    points[8] = [.4 + .2 * pinch_ratio, .3, 0]
    return points


def result(points=None, gesture="Thumb_Up", score=.95, runner_up=None, hands=1):
    categories = [SimpleNamespace(category_name=gesture, score=score)]
    if runner_up:
        categories.append(SimpleNamespace(category_name=runner_up[0], score=runner_up[1]))
    points = points if points is not None else hand(2)
    landmarks = [[SimpleNamespace(x=x, y=y, z=z) for x, y, z in points] for _ in range(hands)]
    return SimpleNamespace(hand_landmarks=landmarks, gestures=[categories for _ in range(hands)])


def test_pinch_ratio_is_distance_normalized_and_ignores_z():
    points = hand(.2)
    ratio, scale = pinch_geometry(points)
    assert ratio == pytest.approx(.2)
    assert scale == pytest.approx(.2)
    scaled = [[.5 + (x - .5) * .5, .5 + (y - .5) * .5, 1000 + z] for x, y, z in points]
    assert pinch_geometry(scaled)[0] == pytest.approx(ratio)
    assert pinch_geometry(scaled)[1] == pytest.approx(scale / 2)


def test_pinch_accounts_for_frame_aspect_ratio():
    points = hand(0)
    points[8][1] += .1
    assert pinch_geometry(points, aspect=2)[0] == pytest.approx(.25)
    assert pinch_geometry(points, aspect=1)[0] == pytest.approx(.5)


def test_missing_or_degenerate_palm_cannot_confirm():
    assert pinch_geometry([]) == (float("inf"), 0)
    points = [[.5, .5, 0] for _ in range(21)]
    assert pinch_geometry(points) == (float("inf"), 0)


def test_interpretation_canned_gesture_and_missing_hand():
    observation, landmarks = interpret_result(result(), 10, 20, Settings())
    assert observation.gesture == "Thumb_Up"
    assert observation.source == "live"
    assert observation.recognition_ms == 20
    assert observation.hand_scale == pytest.approx(.2)
    assert len(landmarks[0]) == 21
    missing, _ = interpret_result(result(hands=0), 11, 21, Settings())
    assert missing.hands == 0 and missing.gesture == "None"


def test_geometric_pinch_uses_explicit_quality_kind():
    observation, _ = interpret_result(result(points=hand(.2), gesture="None", score=.2), 10, 20, Settings())
    assert observation.gesture == "Pinch"
    assert observation.metadata["score_kind"] == "geometric_quality_index"
    assert 0 <= observation.score <= 1
    assert observation.metadata["pinch_eligible"] is True
    assert observation.metadata["raw_canned_gesture"] == "None"


def test_two_hand_geometry_does_not_override_ambiguity_with_pinch():
    observation, _ = interpret_result(result(points=hand(.2), hands=2), 10, 20, Settings())
    assert observation.hands == 2
    assert observation.gesture != "Pinch"


def test_close_classifier_scores_are_ambiguous():
    observation, _ = interpret_result(result(score=.78, runner_up=("Victory", .74)), 10, 20, Settings())
    assert observation.ambiguous is True


def test_missing_model_does_not_start_camera_threads(tmp_path):
    vision = VisionService(tmp_path / "missing.task", Settings())
    with pytest.raises(ValueError, match="model is missing"):
        vision.start()
    assert vision._threads == []
    assert vision.jpeg() is None
    vision.stop()


def test_curled_fist_tip_overlap_is_not_misclassified_as_pinch():
    points = hand(.1)
    points[4] = [.49, .49, 0]
    points[8] = [.50, .49, 0]
    assert pinch_geometry(points)[0] < Settings().pinch_ratio
    assert not pinch_eligible(points)
    observation, _ = interpret_result(result(points=points, gesture="Closed_Fist", score=.93), 10, 20, Settings())
    assert observation.gesture == "Closed_Fist"
    assert observation.metadata["pinch_eligible"] is False
    assert observation.metadata["raw_canned_score"] == .93


def test_strong_fist_classification_is_not_overridden_even_with_projected_tip_overlap():
    observation, _ = interpret_result(result(points=hand(.1), gesture="Closed_Fist", score=.93), 10, 20, Settings())
    assert observation.gesture == "Closed_Fist"


def test_nonfinite_geometry_is_rejected_without_fake_pinch():
    points = hand(.2)
    points[8][0] = float("nan")
    assert pinch_geometry(points) == (float("inf"), 0)
    assert not pinch_eligible(points)
