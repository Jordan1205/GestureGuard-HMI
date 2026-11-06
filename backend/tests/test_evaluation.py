from gestureguard.evaluation import filter_events, summarize, scripted_fixture


def metrics(events):
    return {metric["key"]: metric for metric in summarize(events)["metrics"]}


def test_empty_metrics_do_not_invent_accuracy_or_latency():
    result = metrics([])
    for key in ("recognition_accuracy", "unintended_activations", "false_activations_per_idle_minute", "completion_rate", "task_time", "fps", "command_latency", "recognition_latency"):
        assert result[key]["value"] is None
        assert result[key]["samples"] == 0
    assert result["tracking_losses"]["value"] == 0


def test_metrics_require_labels_and_use_explicit_denominators():
    events = [
        {"id": 1, "type": "command_executed", "details": {"latency_ms": 1200}},
        {"id": 2, "type": "command_label", "details": {"event_id": 1, "intended": False, "idle": True}},
        {"type": "idle_exposure", "details": {"duration_seconds": 120}},
        {"type": "recognition_label", "details": {"predicted": "Victory", "expected": "Victory"}},
        {"type": "recognition_label", "details": {"predicted": "None", "expected": "Pinch"}},
        {"type": "task_result", "details": {"success": True, "duration_seconds": 4}},
        {"type": "task_result", "details": {"success": False, "duration_seconds": 8}},
        {"type": "rejected", "details": {}},
    ]
    result = metrics(events)
    assert result["recognition_accuracy"]["value"] == 50
    assert result["unintended_activations"]["value"] == 1
    assert result["false_activations_per_idle_minute"]["value"] == .5
    assert result["completion_rate"]["value"] == 50
    assert result["task_time"]["value"] == 6
    assert result["rejection_rate"]["value"] == 50
    assert result["command_latency"]["samples"] == 1


def test_duplicate_and_dangling_command_labels_cannot_inflate_counts():
    events = [
        {"id": 1, "type": "command_executed"},
        {"type": "command_label", "details": {"event_id": 1, "intended": False}},
        {"type": "command_label", "details": {"event_id": 1, "intended": True}},
        {"type": "command_label", "details": {"event_id": 99, "intended": False}},
    ]
    assert metrics(events)["unintended_activations"]["value"] == 0
    assert metrics(events)["unintended_activations"]["samples"] == 1


def test_latest_persisted_label_wins_even_when_store_returns_newest_first():
    events = [
        {"id": 3, "type": "command_label", "details": {"event_id": 1, "intended": True}},
        {"id": 2, "type": "command_label", "details": {"event_id": 1, "intended": False}},
        {"id": 1, "type": "command_executed"},
    ]
    assert metrics(events)["unintended_activations"]["value"] == 0


def test_filter_inherits_session_conditions_without_inventing_metadata():
    events = [
        {"type": "session_started", "session_id": "a", "details": {"operator_id": "P01", "lighting": "dim"}},
        {"type": "rejected", "session_id": "a", "mode": "gestureguard"},
        {"type": "command_executed", "session_id": "b", "mode": "baseline"},
    ]
    assert len(filter_events(events, operator_id="P01", lighting="dim")) == 2
    assert len(filter_events(events, lighting="dim", mode="gestureguard")) == 1
    assert filter_events(events, lighting="bright") == []
    assert len(filter_events([{"type": "rejected", "details": {"session": {"operator_id": "P02"}}}], operator_id="P02")) == 1
    assert filter_events(events, mode="all") == events


def test_label_filters_inherit_executed_provenance_and_expected_gesture():
    events = [
        {"id": 1, "type": "command_executed", "mode": "baseline", "gesture": "Thumb_Up", "details": {"source": "live"}},
        {"id": 2, "type": "command_label", "mode": "gestureguard", "gesture": "None", "details": {"event_id": 1, "intended": False, "source": "simulated"}},
        {"id": 3, "type": "recognition_label", "gesture": "None", "details": {"expected": "Pinch", "predicted": "None"}},
    ]
    assert len(filter_events(events, mode="baseline", source="live", gesture="Thumb_Up")) == 2
    assert metrics(filter_events(events, mode="baseline"))["unintended_activations"]["value"] == 1
    assert len(filter_events(events, gesture="Pinch")) == 1


def test_nonfinite_and_injected_performance_are_not_real_measurements():
    events = [
        {"type": "input_observation", "details": {"recognition_ms": 0}},
        {"type": "input_observation", "details": {"recognition_ms": float("nan")}},
        {"type": "performance_sample", "details": {"fps": float("inf")}},
        {"type": "performance_sample", "details": {"fps": 24, "recognition_ms": 13}},
    ]
    result = metrics(events)
    assert result["recognition_latency"]["value"] == 13
    assert result["fps"]["value"] == 24


def test_scripted_fixture_is_deterministic_and_chronological():
    assert scripted_fixture() == scripted_fixture()
    fixture = scripted_fixture()
    assert all(a["timestamp"] < b["timestamp"] for a, b in zip(fixture, fixture[1:]))
    assert any(row["hands"] == 2 for row in fixture)
    assert all(row["source"] == "scripted" for row in fixture)


def test_comparison_repeated_runs_have_identical_outcomes():
    from gestureguard.evaluation import run_comparison
    first, second = run_comparison(), run_comparison()
    assert first["kind"] == "scripted_not_human_benchmark"
    assert first["fixture_hash"] == second["fixture_hash"]
    assert first["config_hash"] == second["config_hash"]
    assert first["results"] == second["results"]
    for row in first["results"]:
        assert next(m for m in row["metrics"] if m["key"] == "recognition_accuracy")["value"] is None
    unintended = {row["mode"]: next(m for m in row["metrics"] if m["key"] == "unintended_activations")["value"] for row in first["results"]}
    assert unintended["baseline"] > unintended["gestureguard"]
    assert unintended["protected"] > unintended["gestureguard"]
