"""Honest event-derived metrics and reproducible control-architecture experiments.

Recognition scores are not probabilities. Recognition accuracy needs a human label;
task success and idle exposure cannot be inferred from an attractive dashboard.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from statistics import mean
from typing import Any, Iterable


FILTERS = ("mode", "session_id", "operator_id", "lighting", "distance", "glove", "gesture", "source")


def _details(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("details", {})
    return value if isinstance(value, dict) else {}


def filter_events(events: Iterable[dict[str, Any]], **filters: str) -> list[dict[str, Any]]:
    """Resolve session metadata before filtering so later annotations stay attributable."""
    rows = list(events)
    sessions = {}
    for row in rows:
        if row.get("type") == "session_started":
            details = _details(row)
            sessions[row.get("session_id")] = {**details.get("session", {}), **details}
    commands = {str(row.get("id")): row for row in rows if row.get("type") == "command_executed"}

    def metadata_for(event: dict[str, Any]) -> dict[str, Any]:
        details = _details(event)
        metadata = {**sessions.get(event.get("session_id"), {}), **details.get("session", {}), **event, **details}
        if event.get("type") == "recognition_label":
            metadata["gesture"] = details.get("gesture") or details.get("expected") or metadata.get("gesture")
        if event.get("type") == "command_label" and str(details.get("event_id")) in commands:
            metadata.update(metadata_for(commands[str(details["event_id"])]))
        return metadata

    result: list[dict[str, Any]] = []
    for event in rows:
        metadata = metadata_for(event)
        if all(filters.get(key) in (None, "", "all") or str(metadata.get(key, "")) == str(filters[key]) for key in FILTERS):
            result.append(event)
    return result


def _numbers(rows: list[dict[str, Any]], event_types: set[str], field: str) -> list[float]:
    result = []
    for event in rows:
        value = _details(event).get(field)
        if event.get("type") in event_types and isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value) and value >= 0:
                result.append(float(value))
    return result


def summarize(events: Iterable[dict[str, Any]], **filters: str) -> dict[str, Any]:
    """Return measured values with sample counts; unavailable measurements are null.

    Annotation types: recognition_label {predicted, expected}; command_label
    {event_id, intended: bool, idle: bool}; idle_exposure {duration_seconds};
    task_result {success: bool, duration_seconds}. Command labels must reference
    an executed event in the same filtered dataset and latest label wins.
    """
    rows = filter_events(events, **filters)
    counts = Counter(str(row.get("type", "unknown")) for row in rows)
    executed = {str(row.get("id")): row for row in rows if row.get("type") == "command_executed"}
    labels: dict[str, dict[str, Any]] = {}
    ordered_rows = sorted(rows, key=lambda row: row["id"]) if rows and all(isinstance(row.get("id"), int) for row in rows) else rows
    for row in ordered_rows:
        details = _details(row)
        if row.get("type") == "command_label" and str(details.get("event_id")) in executed:
            if isinstance(details.get("intended"), bool):
                labels[str(details["event_id"])] = details
    recognition_labels = [
        _details(row) for row in rows if row.get("type") == "recognition_label"
        and isinstance(_details(row).get("expected"), str)
        and isinstance(_details(row).get("predicted"), str)
        and _details(row).get("expected")
    ]
    tasks = [_details(row) for row in rows if row.get("type") == "task_result" and isinstance(_details(row).get("success"), bool)]
    task_times = _numbers(rows, {"task_result"}, "duration_seconds")
    idle_times = _numbers(rows, {"idle_exposure"}, "duration_seconds")
    recognition_times = _numbers(rows, {"input_observation"}, "recognition_ms")
    # Zero is the default for injected observations, not a measured inference time.
    recognition_times = [n for n in recognition_times if n > 0]
    if not recognition_times:
        recognition_times = [n for n in _numbers(rows, {"performance_sample"}, "recognition_ms") if n > 0]
    command_times = _numbers(rows, {"command_executed"}, "latency_ms")
    fps = _numbers(rows, {"performance_sample"}, "fps")
    false_idle = sum(label["intended"] is False and label.get("idle") is True for label in labels.values())
    idle_labels = sum(label.get("idle") is True for label in labels.values())
    total_idle = sum(idle_times)
    metrics: list[dict[str, Any]] = []

    def metric(key: str, label: str, value: float | int | None, unit: str, samples: int, note: str) -> None:
        metrics.append({"key": key, "label": label, "value": round(value, 3) if isinstance(value, float) else value,
                        "unit": unit, "samples": samples, "note": note})

    metric("recognition_accuracy", "Gesture recognition accuracy",
           100 * sum(x["predicted"] == x["expected"] for x in recognition_labels) / len(recognition_labels) if recognition_labels else None,
           "%", len(recognition_labels), "Human-labeled trials only; injected gestures do not measure vision accuracy.")
    metric("unintended_activations", "Unintended activations",
           sum(x["intended"] is False for x in labels.values()) if labels else None,
           "commands", len(labels), "Requires command outcome labels; latest label per executed command wins.")
    metric("false_activations_per_idle_minute", "False activations per idle minute",
           false_idle / (total_idle / 60) if total_idle > 0 and idle_labels else None,
           "commands/min", idle_labels, f"{total_idle:.1f} s annotated idle exposure; only commands labeled idle and unintended count.")
    metric("completion_rate", "Task completion rate",
           100 * sum(x["success"] for x in tasks) / len(tasks) if tasks else None,
           "%", len(tasks), "Requires explicit task_result annotations; rejected gestures are not automatically failed tasks.")
    metric("task_time", "Mean task completion time", mean(task_times) if task_times else None,
           "s", len(task_times), "Timed, annotated tasks; report successful and failed task distributions separately in the report.")
    outcome_count = counts["rejected"] + counts["command_executed"]
    metric("rejection_rate", "Command outcome rejection rate", 100 * counts["rejected"] / outcome_count if outcome_count else None,
           "%", outcome_count, "Rejected events / (rejected + executed events); this is event-based, not a per-frame error rate.")
    metric("tracking_losses", "Tracking loss events", counts["tracking_lost"], "events", counts["tracking_lost"], "Transitions to lost tracking, not missing-camera frame count.")
    metric("fps", "Mean recognition throughput", mean(fps) if fps else None, "fps", len(fps), "Measured live performance samples only; no promised frame rate.")
    metric("command_latency", "Mean end-to-end command latency", mean(command_times) if command_times else None,
           "ms", len(command_times), "Candidate onset to commit, including deliberate holds and confirmation where available.")
    metric("recognition_latency", "Mean recognition latency", mean(recognition_times) if recognition_times else None,
           "ms", len(recognition_times), "Measured inference duration; simulated zero-duration observations excluded.")
    sources = Counter(str(_details(row).get("source", row.get("source", "unspecified"))) for row in rows)
    modes = sorted({str(row["mode"]) for row in rows if row.get("mode")})
    series = []
    for mode in modes:
        mode_counts = Counter(row.get("type") for row in rows if row.get("mode") == mode)
        series.append({"mode": mode, "commands": mode_counts["command_executed"], "rejections": mode_counts["rejected"],
                       "tracking_losses": mode_counts["tracking_lost"]})
    return {"total_events": len(rows), "counts": dict(counts), "source_counts": dict(sources),
            "sessions": sorted({str(row["session_id"]) for row in rows if row.get("session_id")}),
            "modes": modes, "metrics": metrics, "series": series,
            "limitations": "Events describe this application. Scripted/replayed inputs are not human recognition benchmarks."}


def scripted_fixture() -> list[dict[str, Any]]:
    """A shared, deterministic observation stream; no camera/model is involved."""
    segments = [
        ("Thumb_Up", .30, 1, False, "accidental while locked"),
        ("None", .40, 1, False, "release"),
        ("ILoveYou", 1.50, 1, False, "deliberate unlock"),
        ("None", .50, 1, False, "release"),
        ("Thumb_Up", .90, 2, True, "two-hand ambiguity"),
        ("None", .50, 1, False, "release"),
        ("Thumb_Up", .90, 1, False, "intentional start request"),
        ("None", .30, 1, False, "separate confirmation release"),
        ("Pinch", .75, 1, False, "intentional confirmation"),
        ("None", 1.10, 1, False, "release and cooldown"),
        ("Closed_Fist", .90, 1, False, "intentional pause request"),
        ("None", .30, 1, False, "release"),
        ("Pinch", .75, 1, False, "intentional confirmation"),
        ("None", 1.10, 1, False, "release and cooldown"),
        ("Closed_Fist", .90, 1, False, "invalid pause of paused station"),
        ("None", 3.50, 0, False, "sustained hand loss"),
    ]
    result: list[dict[str, Any]] = []
    timestamp = 0.0
    confirmed_action = "start"
    for gesture, duration, hands, ambiguous, annotation in segments:
        if annotation == "intentional pause request":
            confirmed_action = "pause"
        intended_action = confirmed_action if annotation.startswith("intentional") else None
        for _ in range(round(duration / .05)):
            result.append({"timestamp": round(timestamp, 3), "gesture": gesture,
                           "score": .99 if gesture != "None" else 0, "hands": hands,
                           "ambiguous": ambiguous, "source": "scripted", "annotation": annotation,
                           "intended_action": intended_action})
            timestamp += .05
    return result


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def run_comparison() -> dict[str, Any]:
    """Run the same stream through isolated fresh engines, recording actual outcomes."""
    from .domain import Observation, Settings
    from .event_store import EventStore
    from .intent_engine import IntentEngine
    from .simulation import Factory

    fixture = scripted_fixture()
    settings = Settings()
    results = []
    for mode in ("baseline", "protected", "gestureguard"):
        store = EventStore()
        factory = Factory()
        engine = IntentEngine(factory, store, settings=settings, mode=mode, session_id=f"comparison-{mode}")
        previous = fixture[0]["timestamp"]
        for item in fixture:
            observation = {k: v for k, v in item.items() if k != "annotation"}
            engine.process(Observation(**observation))
            factory.tick(item["timestamp"] - previous)
            previous = item["timestamp"]
        events = store.query(limit=100000)
        # The fixture explicitly declares intended actions. These labels are
        # deterministic scenario expectations, not participant judgments.
        for event in events:
            if event["type"] != "command_executed":
                continue
            timestamp = event["monotonic"]
            index = min(max(round(timestamp / .05), 0), len(fixture) - 1)
            expected = fixture[index]["intended_action"]
            store.append({"type": "command_label", "mode": mode,
                          "session_id": f"comparison-{mode}", "monotonic": timestamp,
                          "message": "Scripted expected-intention label; not a human observation.",
                          "details": {"event_id": event["id"], "intended": expected == _details(event).get("action"),
                                      "source": "scripted", "label_origin": "fixture_expectation"}})
        events = store.query(limit=100000)
        summary = summarize(events)
        unintended = next(metric["value"] for metric in summary["metrics"] if metric["key"] == "unintended_activations")
        results.append({"mode": mode, **summary, "commands": summary["counts"].get("command_executed", 0),
                        "rejections": summary["counts"].get("rejected", 0), "unintended_commands": unintended,
                        "final_stations": factory.snapshot(),
                        "final_state": engine.snapshot()["state"]})
        store.close()
    return {"kind": "scripted_not_human_benchmark", "fixture_hash": _digest(fixture),
            "config_hash": _digest(asdict(settings)), "settings": asdict(settings),
            "observations": len(fixture), "results": results,
            "procedure": "Fresh stopped factory and engine per mode; identical 20 Hz labeled scripted observations. Counts test architecture, not recognition accuracy."}
