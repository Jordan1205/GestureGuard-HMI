"""Engineering fixtures only. These tests do not constitute human benchmarks."""
import json

import numpy as np
import pytest

from gestureguard.learning import (FEATURE_VERSION, canonical_label, classification_metrics,
    evaluate_recordings, forest_predict, grouped_split, landmark_features, load_recordings, train_experiment)


def hand():
    return np.array([[0, 0], [-.2,.1],[-.4,.2],[-.5,.4],[-.6,.6],
        [-.3,.5],[-.3,.8],[-.3,1.1],[-.3,1.4],
        [0,.6],[0,1.0],[0,1.4],[0,1.7],
        [.25,.5],[.25,.8],[.25,1.1],[.25,1.35],
        [.45,.4],[.45,.65],[.45,.9],[.45,1.1]])


def test_features_remove_translation_scale_rotation_and_mirroring():
    points = hand()
    reference = landmark_features(points.tolist(), aspect=1)
    angle = .71
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    for transformed in (points * 2.8 + [3,-2], points @ rotation, points * [-1,1]):
        np.testing.assert_allclose(landmark_features(transformed.tolist(), aspect=1), reference, atol=1e-10)
    assert reference.shape == (67,)


def test_features_correct_aspect_and_ignore_uncalibrated_z():
    points = hand()
    stretched = points * [1, 4/3]
    with_z = np.column_stack((stretched, np.arange(21)*300))
    np.testing.assert_allclose(landmark_features(with_z.tolist(), 4/3), landmark_features(points.tolist(), 1))


@pytest.mark.parametrize("points,aspect", [([],1),([[0,0]]*21,1),([[float('nan'),0]]*21,1),(hand().tolist(),0)])
def test_invalid_landmark_features_fail_closed(points, aspect):
    with pytest.raises(ValueError):
        landmark_features(points, aspect)


def test_grouped_split_never_leaks_participant_or_session():
    rows = [{"participant_id":f"P{person}","session_id":f"S{person}","expected":label}
            for person in range(5) for label in ("Thumb_Up","Unknown")]
    split = grouped_split(rows)
    group_sets = [{rows[i]["participant_id"] for i in indices} for indices in split.values()]
    assert all(not a & b for i,a in enumerate(group_sets) for b in group_sets[i+1:])
    assert sorted(i for indices in split.values() for i in indices) == list(range(len(rows)))
    assert split == grouped_split(rows)


def test_inadequate_groups_or_class_coverage_never_fall_back_to_frame_split():
    with pytest.raises(ValueError, match="three independent"):
        grouped_split([{"participant_id":"P1","expected":"Thumb_Up"}])
    with pytest.raises(ValueError, match="lack classes"):
        grouped_split([{"participant_id":f"P{i}","expected":label}
                       for i,label in enumerate(("Thumb_Up","Unknown","Victory"))])


def test_real_recording_loader_excludes_synthetic_and_preserves_group_ids(tmp_path):
    for origin in ("real_webcam","synthetic"):
        directory = tmp_path / origin
        directory.mkdir()
        (directory/"manifest.json").write_text(json.dumps({"origin":origin,"source":"live",
            "participant_id":"P01","session_id":"independent-day-1","label":"Negative"}))
        (directory/"samples.jsonl").write_text(json.dumps({"timestamp":0,"hands":1,"raw_gesture":"Thumb_Up","raw_score":.4})+'\n')
    rows = load_recordings(tmp_path)
    assert len(rows)==1 and rows[0]["expected"]=="Unknown"
    assert rows[0]["recording_label"]=="Negative"
    assert rows[0]["session_id"]=="independent-day-1"


def test_loader_rejects_nonmonotonic_recording(tmp_path):
    (tmp_path/"manifest.json").write_text(json.dumps({"origin":"real_webcam","source":"live",
        "participant_id":"P01","session_id":"S1","label":"Thumb_Up"}))
    (tmp_path/"samples.jsonl").write_text('\n'.join(json.dumps({"timestamp":t}) for t in (2,1)))
    with pytest.raises(ValueError,match="timestamps"):
        load_recordings(tmp_path)


def test_metrics_distinguish_unknown_rejection_and_undefined_precision():
    report=classification_metrics(["Thumb_Up","Thumb_Up","Unknown"],["Thumb_Up","Unknown","Unknown"])
    assert report["per_gesture"]["Thumb_Up"]=={"precision":1,"recall":.5,"support":2}
    assert report["unknown_rejection_rate"]==1
    assert sum(map(sum,report["confusion_matrix"]))==3
    assert classification_metrics([],[])["accuracy"] is None
    with pytest.raises(ValueError):
        classification_metrics(["Thumb_Up"],[])


def leaf_forest(threshold=.7):
    return {"format":"gestureguard-numeric-forest-v1","feature_version":FEATURE_VERSION,
        "classes":["Thumb_Up","Unknown"],"features":67,"threshold":threshold,
        "trees":[{"left":[-1],"right":[-1],"feature":[-2],"threshold":[-2],"value":[[3,1]]}]}


def test_numeric_json_forest_inference_and_rejection_without_unpickling():
    assert forest_predict(leaf_forest(),np.zeros(67))==("Thumb_Up",.75)
    assert forest_predict(leaf_forest(.8),np.zeros(67))==("Unknown",.75)
    forest=leaf_forest()
    forest["trees"][0].update(left=[0],right=[0],feature=[0],threshold=[0])
    with pytest.raises(ValueError,match="depth/cycle"):
        forest_predict(forest,np.zeros(67))


def test_training_without_data_does_not_fabricate_a_model():
    with pytest.raises(ValueError,match="No usable"):
        train_experiment([])
    assert evaluate_recordings([])["status"]=="no_human_recordings"
    assert evaluate_recordings([])["command_false_activation_rate"] is None


def test_evaluation_requires_held_out_groups_and_rejects_model_leakage():
    rows=[{"participant_id":"P1","recording_id":"clip","expected":"Thumb_Up","timestamp":0}]
    with pytest.raises(ValueError,match="held-out"):
        evaluate_recordings(rows)
    artifact=leaf_forest()
    artifact["metadata"]={"group_by":"participant_id","groups":{"train":["P1"],"validation":[]}}
    with pytest.raises(ValueError,match="overlap"):
        evaluate_recordings(rows,{"P1"},artifact=artifact)


def test_scripted_low_score_fixture_exercises_hold_math_not_human_performance():
    rows=[{"participant_id":"fixture","session_id":"fixture","recording_id":"synthetic-engineering-fixture",
        "expected":"Thumb_Up","raw_gesture":"Thumb_Up","raw_score":.6,"hands":1,"timestamp":i*.05,
        "recognition_ms":0} for i in range(45)]
    report=evaluate_recordings(rows,{"fixture"})
    assert report["raw_mediapipe"]["accuracy"]==1
    assert report["original_hold_component"]["completed_gesture_holds"]==0
    assert report["improved_hold_component"]["completed_gesture_holds"]==1
    assert report["successful_command_completion_rate"] is None
    assert report["recognition_latency_ms"] is None
    assert canonical_label("Neutral")=="Unknown"


def test_recorded_contract_separates_canned_model_from_pinch_geometry():
    rows=[{"participant_id":"fixture","session_id":"fixture","recording_id":"geometry-unit-fixture",
        "expected":"Pinch","raw_gesture":"None","raw_score":.2,
        "raw_canned_gesture":"None","raw_canned_score":.2,
        "gesture":"Pinch","score":.1,"hands":1,"timestamp":i*.05,
        "pinch_ratio":.1,"pinch_eligible":True,"score_kind":"geometric_quality_index"} for i in range(30)]
    report=evaluate_recordings(rows,{"fixture"})
    assert report["raw_canned_mediapipe"]["accuracy"]==0
    assert report["original_hold_component"]["completed_gesture_holds"]==1
    assert report["improved_hold_component"]["completed_gesture_holds"]==1
    assert report["improved_filtered_candidates"]["accuracy"]==1
