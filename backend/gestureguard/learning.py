"""Local-only landmark experiments. Nothing here replaces the live recognizer.

Dataset splits are grouped by person or independent recording session. Framewise
splitting would leak near-duplicate hand poses into the test set. Forest artifacts
are numeric JSON, not executable pickle/joblib files.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Any, Iterable

import numpy as np

COMMAND_LABELS = ("Open_Palm", "Closed_Fist", "Thumb_Up", "Victory", "Pointing_Up", "Pinch", "ILoveYou")
NEGATIVE_LABELS = {"None", "Neutral", "Negative", "Unknown", "neutral", "negative", "no_gesture"}
FEATURE_VERSION = "image2d-joints-v1"


def canonical_label(label: str) -> str:
    if label in COMMAND_LABELS:
        return label
    if label in NEGATIVE_LABELS:
        return "Unknown"
    raise ValueError(f"Unsupported recording label: {label}")


def landmark_features(landmarks: list, aspect: float = 4 / 3) -> np.ndarray:
    """67 image-space features: normalized xy, projected joint cosines, tip gaps.

    Position, uniform scale, in-plane rotation, and left/right reflection are
    normalized. Camera-depth z is deliberately unused; this does not claim
    invariance to out-of-plane pose, perspective, occlusion, or physical distance.
    """
    points = np.asarray(landmarks, dtype=float)
    if points.shape not in {(21, 2), (21, 3)} or not np.isfinite(points).all():
        raise ValueError("One finite 21-point hand is required.")
    if not math.isfinite(aspect) or aspect <= 0:
        raise ValueError("Image aspect must be finite and positive.")
    xy = points[:, :2].copy()
    xy[:, 1] /= aspect
    xy -= xy[0]
    forward = xy[9]
    scale = float(np.linalg.norm(forward))
    if scale < 1e-6 or np.linalg.norm(xy[5] - xy[17]) < 1e-6:
        raise ValueError("Degenerate palm geometry.")
    forward = forward / scale
    side = np.array([forward[1], -forward[0]])
    if float(xy[5] @ side) < 0:
        side *= -1
    normalized = np.column_stack((xy @ side, xy @ forward)) / scale
    angles = []
    chains = ((0, 1, 2, 3, 4), (0, 5, 6, 7, 8), (0, 9, 10, 11, 12),
              (0, 13, 14, 15, 16), (0, 17, 18, 19, 20))
    for chain in chains:
        for a, b, c in zip(chain, chain[1:], chain[2:]):
            u, v = normalized[a] - normalized[b], normalized[c] - normalized[b]
            denominator = float(np.linalg.norm(u) * np.linalg.norm(v))
            angles.append(float(np.clip(u @ v / denominator, -1, 1)) if denominator > 1e-9 else 0.0)
    tips = (4, 8, 12, 16, 20)
    gaps = [float(np.linalg.norm(normalized[a] - normalized[b]))
            for i, a in enumerate(tips) for b in tips[i + 1:]]
    return np.concatenate((normalized.reshape(-1), angles, gaps))


def load_recordings(directory: str | Path) -> list[dict[str, Any]]:
    """Read only opt-in real-webcam manifests; never infer consent from filenames."""
    root = Path(directory)
    rows = []
    for manifest_path in sorted(root.rglob("manifest.json")) if root.exists() else []:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("origin") != "real_webcam" or manifest.get("source", "live") != "live":
            continue
        if not manifest.get("participant_id") or not manifest.get("session_id"):
            raise ValueError(f"Recording lacks participant/session identity: {manifest_path.parent.name}")
        sample_path = manifest_path.parent / "samples.jsonl"
        if not sample_path.exists():
            continue
        previous = -math.inf
        for line_number, line in enumerate(sample_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source", "live") != "live" or row.get("origin", "real_webcam") != "real_webcam":
                continue
            timestamp = float(row.get("timestamp", 0))
            if not math.isfinite(timestamp) or timestamp < previous:
                raise ValueError(f"Recording timestamps must be finite/nondecreasing: {sample_path.name}:{line_number}")
            previous = timestamp
            expected = row.get("expected", row.get("label", manifest.get("label")))
            canonical = canonical_label(str(expected))
            rows.append({**manifest, **row, "participant_id": manifest["participant_id"],
                "session_id": manifest["session_id"], "recording_id": manifest_path.parent.name,
                "expected": canonical, "recording_label": expected, "timestamp": timestamp})
    return rows


def grouped_split(rows: list[dict], group_by: str = "participant_id", seed: int = 42) -> dict[str, list[int]]:
    """A fixed grouped split, with explicit coverage checks rather than silent leakage."""
    if group_by not in {"participant_id", "session_id"}:
        raise ValueError("Group by participant_id or session_id.")
    groups = sorted({str(row.get(group_by, "")) for row in rows})
    if "" in groups or len(groups) < 3:
        raise ValueError("Collect at least three independent participant/session groups, each covering the vocabulary.")
    random.Random(seed).shuffle(groups)
    held = max(1, len(groups) // 5)
    assignments = {"test": set(groups[:held]), "validation": set(groups[held:held * 2]),
                   "train": set(groups[held * 2:])}
    result = {name: [i for i, row in enumerate(rows) if str(row[group_by]) in values]
              for name, values in assignments.items()}
    labels = {row["expected"] for row in rows}
    for name, indices in result.items():
        missing = labels - {rows[i]["expected"] for i in indices}
        if missing:
            raise ValueError(f"{name} groups lack classes {sorted(missing)}. Collect full-vocabulary independent sessions; do not move frames across groups.")
    return result


def classification_metrics(expected: Iterable[str], predicted: Iterable[str]) -> dict[str, Any]:
    truth, output = list(expected), list(predicted)
    if len(truth) != len(output):
        raise ValueError("Prediction and label sample counts differ.")
    labels = sorted(set(truth) | set(output))
    matrix = [[sum(a == actual and b == forecast for a, b in zip(truth, output))
               for forecast in labels] for actual in labels]
    per_class = {}
    for i, name in enumerate(labels):
        support, proposed, correct = sum(matrix[i]), sum(row[i] for row in matrix), matrix[i][i]
        per_class[name] = {"precision": correct / proposed if proposed else None,
                           "recall": correct / support if support else None, "support": support}
    unknown = [b for a, b in zip(truth, output) if a == "Unknown"]
    return {"samples": len(truth), "accuracy": sum(a == b for a, b in zip(truth, output)) / len(truth) if truth else None,
            "labels": labels, "confusion_matrix": matrix, "per_gesture": per_class,
            "unknown_rejection_rate": sum(x == "Unknown" for x in unknown) / len(unknown) if unknown else None,
            "unknown_samples": len(unknown),
            "note": "Frame classification metrics, not command completion or safety probabilities."}


def forest_to_json(model, threshold: float, metadata: dict) -> dict:
    """Export numeric forest structure; loading never invokes Python object deserialization."""
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        trees.append({"left": tree.children_left.tolist(), "right": tree.children_right.tolist(),
                      "feature": tree.feature.tolist(), "threshold": tree.threshold.tolist(),
                      "value": tree.value[:, 0, :].tolist()})
    return {"format": "gestureguard-numeric-forest-v1", "feature_version": FEATURE_VERSION,
            "classes": [str(x) for x in model.classes_], "threshold": threshold,
            "features": int(model.n_features_in_), "trees": trees, "metadata": metadata}


def forest_predict(artifact: dict, features: np.ndarray) -> tuple[str, float]:
    """Bounded JSON-tree inference; returned vote score is not calibrated probability."""
    if not isinstance(artifact, dict) or artifact.get("format") != "gestureguard-numeric-forest-v1" or artifact.get("feature_version") != FEATURE_VERSION:
        raise ValueError("Unsupported classifier artifact format.")
    vector = np.asarray(features, dtype=float)
    classes, trees = artifact.get("classes", []), artifact.get("trees", [])
    threshold = float(artifact.get("threshold", 1))
    if vector.shape != (67,) or not np.isfinite(vector).all() or artifact.get("features") != 67:
        raise ValueError("Classifier expects 67 finite versioned features.")
    if not isinstance(trees, list) or not isinstance(classes, list) or not 1 <= len(trees) <= 128 or not classes or len(classes) > 32 or not 0 <= threshold <= 1:
        raise ValueError("Invalid forest size, classes, or threshold.")
    if any(not isinstance(name, str) or name not in set(COMMAND_LABELS) | {"Unknown"} for name in classes):
        raise ValueError("Forest contains an unsupported gesture class.")
    votes = np.zeros(len(classes))
    for tree in trees:
        if not isinstance(tree, dict):
            raise ValueError("Tree must be a numeric object.")
        lengths = {len(tree.get(key, [])) for key in ("left", "right", "feature", "threshold", "value")}
        if len(lengths) != 1 or not 1 <= next(iter(lengths)) <= 8191:
            raise ValueError("Invalid JSON tree arrays.")
        node = 0
        for _ in range(32):
            left, right = int(tree["left"][node]), int(tree["right"][node])
            if left == right == -1:
                value = np.asarray(tree["value"][node], dtype=float)
                if value.shape != votes.shape or not np.isfinite(value).all() or np.any(value < 0) or value.sum() <= 0:
                    raise ValueError("Invalid leaf votes.")
                votes += value / value.sum()
                break
            feature = int(tree["feature"][node])
            cut = float(tree["threshold"][node])
            if not 0 <= feature < 67 or not math.isfinite(cut):
                raise ValueError("Invalid tree decision.")
            node = left if vector[feature] <= cut else right
            if not 0 <= node < next(iter(lengths)):
                raise ValueError("Tree child index is invalid.")
        else:
            raise ValueError("Tree depth/cycle exceeds the limit.")
    votes /= len(trees)
    top = int(np.argmax(votes))
    return (str(classes[top]) if votes[top] >= threshold else "Unknown", float(votes[top]))


def train_experiment(rows: list[dict], group_by: str = "participant_id", seed: int = 42) -> tuple[dict, dict]:
    usable = []
    features = []
    for row in rows:
        if row.get("hands", 1) != 1:
            continue
        try:
            vector = landmark_features(row.get("landmarks", []), float(row.get("aspect", 4 / 3)))
        except (ValueError, TypeError):
            continue
        usable.append(row)
        features.append(vector)
    if not usable:
        raise ValueError("No usable labeled human hand recordings. Record real examples first.")
    required = set(COMMAND_LABELS) | {"Unknown"}
    missing = required - {r["expected"] for r in usable}
    if missing:
        raise ValueError(f"Missing required positive/negative classes: {sorted(missing)}")
    split = grouped_split(usable, group_by, seed)
    try:
        from sklearn.ensemble import RandomForestClassifier
        import sklearn
    except ImportError as exc:
        raise ValueError("Optional training dependencies are absent. Install requirements-training.txt before training.") from exc
    x = np.asarray(features)
    y = np.asarray([row["expected"] for row in usable])
    model = RandomForestClassifier(n_estimators=64, max_depth=10, min_samples_leaf=3,
                                   class_weight="balanced", random_state=seed, n_jobs=1)
    model.fit(x[split["train"]], y[split["train"]])
    # Threshold selection uses validation only; test groups stay untouched.
    probabilities = model.predict_proba(x[split["validation"]])
    choices = []
    for threshold in (.5, .6, .7, .8, .9):
        predicted = [str(model.classes_[int(np.argmax(p))]) if max(p) >= threshold else "Unknown" for p in probabilities]
        metrics = classification_metrics(y[split["validation"]].tolist(), predicted)
        known_recalls = [v["recall"] for key, v in metrics["per_gesture"].items() if key != "Unknown" and v["recall"] is not None]
        unknown = metrics["unknown_rejection_rate"]
        # Require negative support; preserve rejection before optimizing command recall.
        objective = ((unknown if unknown is not None else -1), mean(known_recalls) if known_recalls else 0)
        choices.append((objective, threshold, metrics))
    _, threshold, validation = max(choices, key=lambda item: (item[0], -item[1]))
    groups = {name: sorted({str(usable[i][group_by]) for i in indices}) for name, indices in split.items()}
    fingerprint = sha256(json.dumps([{k: row.get(k) for k in ("participant_id", "session_id", "recording_id", "timestamp", "expected", "landmarks")}
                                    for row in usable], sort_keys=True).encode()).hexdigest()
    metadata = {"seed": seed, "group_by": group_by, "groups": groups, "data_sha256": fingerprint,
                "sklearn_version": sklearn.__version__, "activation": "offline_only_not_selected_for_live_control"}
    artifact = forest_to_json(model, threshold, metadata)
    test_predictions = [forest_predict(artifact, x[i])[0] for i in split["test"]]
    report = {"status": "trained_offline_not_deployed", "metadata": metadata, "threshold": threshold,
              "samples": len(usable), "skipped_samples": len(rows) - len(usable),
              "validation": validation, "test": classification_metrics(y[split["test"]].tolist(), test_predictions),
              "limitations": "Human held-out classification only. Live deployment needs independent end-to-end and idle-motion validation; no automatic replacement."}
    return artifact, report


def evaluate_recordings(rows: list[dict], held_out_groups: set[str] | None = None,
                        group_by: str = "participant_id", artifact: dict | None = None, settings=None) -> dict:
    """Paired outputs on identical human samples; classification and intent stay separate.

    Static labeled clips cannot establish completed factory tasks or command false
    activations. Those remain unavailable. Hold completion is a narrower component
    measure comparing the original hard-gate/release rule with current evidence.
    """
    from .domain import Observation, Settings
    from .temporal_filter import TemporalFilter
    if not rows:
        return {"status": "no_human_recordings", "samples": 0, "raw_mediapipe": classification_metrics([], []),
                "command_false_activation_rate": None, "successful_command_completion_rate": None,
                "note": "No real-human benchmark was run. Collect consented independent training/validation/test sessions first."}
    if group_by not in {"participant_id", "session_id"} or not held_out_groups:
        raise ValueError("Explicit held-out participant/session groups are required for recognition evaluation.")
    if artifact:
        metadata = artifact.get("metadata", {})
        if metadata.get("group_by") != group_by:
            raise ValueError("Evaluation grouping must match model training grouping.")
        excluded = set(metadata.get("groups", {}).get("train", [])) | set(metadata.get("groups", {}).get("validation", []))
        if excluded & held_out_groups:
            raise ValueError("Evaluation groups overlap model training/validation groups.")
    selected = [row for row in rows if str(row.get(group_by)) in held_out_groups]
    if not selected:
        raise ValueError("No records match the held-out groups.")
    settings = settings or Settings()
    clips: dict[str, list[dict]] = {}
    for row in selected:
        clips.setdefault(str(row["recording_id"]), []).append(row)
    truth, raw_outputs, gated_outputs, filtered_outputs, custom_outputs = [], [], [], [], []
    canned_truth, canned_outputs = [], []
    original_success = improved_success = original_interruptions = improved_interruptions = target_clips = 0
    original_times, improved_times = [], []
    conditions: dict[str, dict] = {}
    for recording_id, clip in clips.items():
        clip.sort(key=lambda row: row["timestamp"])
        temporal = TemporalFilter()
        since = None
        previous = None
        release_required = False
        original_finished = improved_finished = False
        target = clip[0]["expected"]
        is_target = target != "Unknown"
        target_clips += is_target
        duration = settings.unlock_seconds if target == "ILoveYou" else settings.confirm_seconds if target == "Pinch" else settings.hold_seconds
        started = clip[0]["timestamp"]
        for row in clip:
            timestamp = float(row["timestamp"])
            canned = str(row.get("raw_canned_gesture", row.get("raw_gesture", row.get("gesture", "None"))))
            canned_score = float(row.get("raw_canned_score", row.get("raw_score", row.get("score", 0))))
            raw = str(row.get("gesture", canned))
            score = float(row.get("score", canned_score))
            hands = int(row.get("hands", 0))
            ambiguous = bool(row.get("ambiguous", False))
            if not math.isfinite(score) or not 0 <= score <= 1 or not math.isfinite(canned_score) or not 0 <= canned_score <= 1:
                raise ValueError("Recorded raw scores must be finite and in 0–1.")
            raw_output = canned if canned in COMMAND_LABELS and hands == 1 and not ambiguous else "Unknown"
            legacy_raw, legacy_score = canned, canned_score
            ratio = row.get("pinch_ratio", row.get("metadata", {}).get("pinch_ratio"))
            # Reproduce the original427707e geometry override/quality scale, including
            # its lack of a curled-fist extension guard, rather than feeding it the
            # new geometry score and pretending the two scales are interchangeable.
            if isinstance(ratio, (int, float)) and math.isfinite(ratio) and 0 <= ratio <= settings.pinch_ratio and hands == 1:
                legacy_raw = "Pinch"
                legacy_score = 1.0 - .3 * ratio / settings.pinch_ratio
            threshold = settings.min_score
            legacy_known = legacy_raw in COMMAND_LABELS and hands == 1 and not ambiguous
            gated = legacy_raw if legacy_known and legacy_score >= threshold else "Unknown"
            if legacy_raw in {"None", "Open_Palm"} or hands == 0:
                release_required = False
            if gated == "Unknown":
                if since is not None:
                    original_interruptions += 1
                since = None
                if legacy_known and legacy_score < threshold:
                    release_required = True
            elif not release_required:
                if previous != legacy_raw or since is None:
                    since = timestamp
                if is_target and legacy_raw == target and timestamp - since + 1e-9 >= duration and not original_finished:
                    original_success += 1
                    original_times.append(timestamp - started)
                    original_finished = True
            else:
                since = None
            previous = legacy_raw
            metadata = dict(row.get("metadata", {}))
            for key in ("score_kind", "pinch_eligible", "pinch_ratio", "raw_canned_gesture", "raw_canned_score"):
                if key in row:
                    metadata[key] = row[key]
            evidence = temporal.update(Observation(timestamp, raw, score, hands, ambiguous, "live", metadata=metadata), settings)
            accepted, _, _ = temporal.accepted(evidence, duration, settings)
            filtered = evidence.gesture if evidence.fresh_supported else "Unknown"
            if filtered not in COMMAND_LABELS:
                filtered = "Unknown"
            if is_target and accepted and evidence.gesture == target and not improved_finished:
                improved_success += 1
                improved_times.append(timestamp - started)
                improved_finished = True
            truth.append(row["expected"])
            canned_truth.append(row["expected"])
            canned_outputs.append(raw_output)
            raw_outputs.append(raw_output)
            gated_outputs.append(gated)
            filtered_outputs.append(filtered)
            condition_key = json.dumps({k: row.get(k, "unspecified") for k in ("lighting", "distance", "glove", "participant_id")}, sort_keys=True)
            condition = conditions.setdefault(condition_key, {"expected": [], "predicted": []})
            condition["expected"].append(row["expected"])
            condition["predicted"].append(raw_output)
            if artifact:
                if hands == 1:
                    try:
                        prediction, _ = forest_predict(artifact, landmark_features(row.get("landmarks", []), float(row.get("aspect", 4 / 3))))
                    except (ValueError, TypeError):
                        prediction = "Unknown"
                else:
                    prediction = "Unknown"
                custom_outputs.append(prediction)
        improved_interruptions += temporal.interruptions
    inference_ms = [float(row["recognition_ms"]) for row in selected
                    if isinstance(row.get("recognition_ms"), (int, float)) and math.isfinite(row["recognition_ms"]) and row["recognition_ms"] > 0]
    def completion(successes, times, interruptions):
        return {"completed_gesture_holds": successes, "target_clips": target_clips,
                "gesture_hold_completion_rate": successes / target_clips if target_clips else None,
                "mean_time_to_gesture_hold_seconds": mean(times) if times else None,
                "hold_interruptions": interruptions}
    return {"status": "measured_human_recordings", "samples": len(selected), "recordings": len(clips),
            "group_by": group_by, "held_out_groups": sorted(held_out_groups), "settings": settings.to_dict(),
            "raw_mediapipe": classification_metrics(truth, raw_outputs),
            "raw_canned_mediapipe": classification_metrics(canned_truth, canned_outputs) if canned_truth else None,
            "original_hard_gate_output": classification_metrics(truth, gated_outputs),
            "improved_filtered_candidates": classification_metrics(truth, filtered_outputs),
            "original_hold_component": completion(original_success, original_times, original_interruptions),
            "improved_hold_component": completion(improved_success, improved_times, improved_interruptions),
            "custom_classifier": classification_metrics(truth, custom_outputs) if artifact else None,
            "recognition_latency_ms": mean(inference_ms) if inference_ms else None,
            "command_false_activation_rate": None, "successful_command_completion_rate": None,
            "mean_time_to_successful_command_seconds": None,
            "conditions_raw_mediapipe": [{"conditions": json.loads(key), "metrics": classification_metrics(value["expected"], value["predicted"])}
                                         for key, value in sorted(conditions.items())],
            "limitations": "raw_mediapipe/raw_canned_mediapipe describe the unchanged canned model; its vocabulary has no Pinch. improved_filtered_candidates describes fresh supported candidates from interpreted gesture/score (including geometry), not committed actions or changed raw model accuracy. Original hard gating reconstructs427707e pinch override from recorded tip ratio using its old quality scale. Hold completion isolates the score/stability subsystem, not the entire original FSM. Static labeled clips cannot establish factory-task completion, command false activations or idle exposure; use annotated full interaction trials for those."}
