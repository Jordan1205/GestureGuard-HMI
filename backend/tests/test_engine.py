import json
import math

import pytest

from gestureguard.domain import Observation, Settings, State
from gestureguard.event_store import EventStore
from gestureguard.intent_engine import IntentEngine, VALID_TRANSITIONS
from gestureguard.simulation import Factory


def make(mode="gestureguard"):
    factory, store = Factory(), EventStore()
    # Preserve the original hard-gate reference tests. The improved causal path
    # is exercised with densely timestamped streams in test_temporal_filter.py.
    return IntentEngine(factory, store, settings=Settings(temporal_filter_enabled=False), mode=mode)


def observe(engine, timestamp, gesture="None", hands=1, **kwargs):
    engine.process(Observation(timestamp, gesture, score=kwargs.pop("score", .99), hands=hands, **kwargs))


def unlock(engine, start=0):
    observe(engine, start, "ILoveYou")
    observe(engine, start + 1.2, "ILoveYou")
    observe(engine, start + 1.3)


def preview(engine, start=2, gesture="Thumb_Up"):
    observe(engine, start, gesture)
    observe(engine, start + .65, gesture)


def events(engine, kind):
    return engine.store.query(type=kind)


def test_full_gestureguard_lifecycle_requires_separate_confirm():
    engine = make()
    assert engine.state == State.LOCKED
    unlock(engine)
    preview(engine)
    assert engine.state == State.AWAITING_CONFIRMATION
    assert engine.factory.stations[0].state == "stopped"
    observe(engine, 3, "Thumb_Up")
    assert not events(engine, "command_executed")
    observe(engine, 3.1, "Pinch")
    observe(engine, 3.6, "Pinch")
    assert engine.state == State.COOLDOWN
    assert engine.factory.stations[0].state == "running"
    executed = events(engine, "command_executed")
    assert len(executed) == 1
    assert executed[0]["details"]["latency_ms"] == 1600
    states = [row["details"]["state"] for row in reversed(events(engine, "state_changed"))]
    assert State.ACTION_PREVIEW in states
    assert State.EXECUTING in states


def test_all_logged_transitions_are_valid():
    engine = make()
    unlock(engine)
    preview(engine)
    observe(engine, 3, "Open_Palm")
    engine.lock()
    for event in events(engine, "state_changed"):
        detail = event["details"]
        assert State(detail["state"]) in VALID_TRANSITIONS[State(detail["previous"])]
    with pytest.raises(ValueError, match="Invalid state transition"):
        engine._transition(State.AWAITING_CONFIRMATION)


def test_unstable_gesture_never_previews():
    engine = make()
    unlock(engine)
    observe(engine, 2, "Thumb_Up")
    observe(engine, 2.2)
    observe(engine, 2.3, "Thumb_Up")
    observe(engine, 2.8, "Thumb_Up")
    assert not engine.pending


def test_repeated_gesture_is_suppressed_until_release_and_cooldown():
    engine = make("protected")
    unlock(engine)
    preview(engine)
    for timestamp in (2.8, 3.8, 4.8, 5.8):
        observe(engine, timestamp, "Thumb_Up")
    assert len(events(engine, "command_executed")) == 1
    observe(engine, 6)
    observe(engine, 6.1, "Closed_Fist")
    observe(engine, 6.75, "Closed_Fist")
    assert engine.factory.stations[0].state == "paused"
    assert len(events(engine, "command_executed")) == 2


def test_confirmation_timeout():
    engine = make()
    unlock(engine)
    preview(engine)
    engine.tick(8.65)
    assert engine.pending is None
    assert engine.state == State.REJECTED
    assert "timeout" in engine.reason.lower()
    assert engine.factory.stations[0].state == "stopped"


def test_tracking_loss_cancels_then_locks():
    engine = make()
    unlock(engine)
    preview(engine)
    observe(engine, 3, hands=0)
    assert engine.pending is None
    assert "Tracking lost" in engine.reason
    assert len(events(engine, "tracking_lost")) == 1
    observe(engine, 3.5, hands=0)
    assert len(events(engine, "tracking_lost")) == 1
    engine.tick(6)
    assert engine.state == State.LOCKED
    assert len(events(engine, "auto_lock")) == 1


def test_context_switch_cancels_pending_command():
    engine = make()
    unlock(engine)
    preview(engine)
    assert engine.manual("select", "conveyor")[0]
    assert engine.factory.selected == 1
    assert engine.pending is None
    assert any("Selected station changed" in row["message"] for row in events(engine, "rejected"))
    assert not engine.manual("confirm")[0]


def test_external_context_switch_is_revalidated_on_tick():
    engine = make()
    unlock(engine)
    preview(engine)
    engine.factory.select(2)
    engine.tick(3)
    assert not engine.pending
    assert "station changed" in engine.reason


def test_invalid_pause_is_rejected_before_preview():
    engine = make()
    unlock(engine)
    preview(engine, gesture="Closed_Fist")
    assert engine.state == State.REJECTED
    assert "pause requires a running station" in engine.reason
    assert not events(engine, "action_proposed")


def test_permission_is_revalidated_at_confirmation():
    engine = make()
    unlock(engine)
    preview(engine)
    engine.factory.command("start")
    observe(engine, 3, "Pinch")
    observe(engine, 3.5, "Pinch")
    assert engine.state == State.REJECTED
    assert "already running" in engine.reason
    assert not events(engine, "command_executed")


@pytest.mark.parametrize("extra,reason", [
    ({"hands": 2}, "Multiple hands"),
    ({"ambiguous": True}, "Ambiguous"),
    ({"score": .2}, "quality threshold"),
    ({"hand_scale": .01}, "operating range"),
])
def test_uncertainty_rejection(extra, reason):
    engine = make()
    unlock(engine)
    observe(engine, 2, "Thumb_Up", **extra)
    assert reason in engine.reason
    assert not engine.pending


def test_locked_command_cannot_execute():
    engine = make()
    observe(engine, 1, "Thumb_Up")
    observe(engine, 3, "Thumb_Up")
    assert engine.state == State.LOCKED
    assert engine.factory.stations[0].state == "stopped"


def test_mode_differences_on_equivalent_input_stream():
    engines = [make(mode) for mode in ("baseline", "protected", "gestureguard")]
    for engine in engines:
        observe(engine, 0, "Thumb_Up")
        observe(engine, .1, "Thumb_Up")
    assert engines[0].factory.stations[0].state == "running"
    assert all(e.factory.stations[0].state == "stopped" for e in engines[1:])
    for engine in engines[1:]:
        unlock(engine, start=1)
        preview(engine, start=3)
    assert engines[1].factory.stations[0].state == "running"
    assert engines[2].factory.stations[0].state == "stopped"
    assert engines[2].pending is not None


def test_manual_fallback_works_without_camera_and_has_explicit_preview():
    engine = make()
    assert engine.manual("start")[0]
    assert engine.pending
    observe(engine, .1, hands=0)
    assert engine.pending
    assert engine.manual("confirm")[0]
    assert engine.factory.stations[0].state == "running"
    assert engine.manual("stop")[0]
    assert engine.factory.stations[0].state == "stopped"
    assert events(engine, "command_executed")[0]["details"]["source"] == "manual"


def test_gesture_station_selection_is_debounced():
    engine = make()
    unlock(engine)
    preview(engine, gesture="Victory")
    assert engine.factory.selected == 1
    observe(engine, 4, "Victory")
    assert engine.factory.selected == 1
    observe(engine, 4.1)
    preview(engine, start=5, gesture="Pointing_Up")
    assert engine.factory.selected == 0


def test_open_palm_cancels():
    engine = make()
    unlock(engine)
    preview(engine)
    observe(engine, 3, "Open_Palm")
    assert not engine.pending
    assert engine.state == State.READY
    assert not events(engine, "command_executed")


def test_inactivity_auto_lock_uses_elapsed_time():
    engine = make()
    unlock(engine)
    observe(engine, 2, "None")
    engine.tick(31.2)
    assert engine.state == State.LOCKED
    assert "Inactivity" in engine.reason


def test_event_serialization_and_filtered_persistence(tmp_path):
    path = tmp_path / "audit.sqlite3"
    store = EventStore(path)
    event = store.append({"mode": "protected", "session_id": "s1", "gesture": "Pinch", "message": "Confirmed", "details": {"operator_id": "P03", "nested": [1, {"ok": True}]}})
    assert json.loads(json.dumps(event)) == event
    store.close()
    store = EventStore(path)
    assert store.query(operator_id="P03", mode="protected", search="confirmed")[0] == event
    assert store.query(operator_id="P99") == []
    assert store.query(limit=0) == []
    store.close()


def test_logged_observation_replay_is_consistent():
    original = make()
    unlock(original)
    preview(original)
    observe(original, 3, "Pinch")
    observe(original, 3.5, "Pinch")
    replay = make()
    for event in reversed(events(original, "input_observation")):
        replay.process(Observation(**event["details"]))
    assert replay.factory.snapshot() == original.factory.snapshot()
    assert replay.snapshot() == original.snapshot()
    first = [(e["type"], e["monotonic"], e["message"]) for e in reversed(original.events) if e["type"] != "input_observation"]
    second = [(e["type"], e["monotonic"], e["message"]) for e in reversed(replay.events) if e["type"] != "input_observation"]
    assert first == second


def test_factory_is_deterministic_and_pause_preserves_counters():
    factory = Factory()
    assert factory.command("start", "conveyor")[0]
    factory.tick(10)
    assert factory.station("conveyor").items == 3
    assert factory.command("pause", "conveyor")[0]
    before = factory.snapshot()
    factory.tick(10)
    assert factory.snapshot() == before
    second = Factory()
    second.command("start", "conveyor")
    for _ in range(100):
        second.tick(.1)
    assert second.station("conveyor").items == 3
    assert second.station("conveyor").progress == pytest.approx(factory.station("conveyor").progress)


def test_inspection_pattern_and_reset():
    factory = Factory()
    factory.command("start", "inspection")
    factory.tick(100)
    station = factory.station("inspection")
    assert station.items == 26
    assert station.failed == 3
    assert station.passed == 23
    factory.reset()
    assert all(s.state == "stopped" and s.items == 0 for s in factory.stations)


def test_settings_and_time_validation():
    with pytest.raises(ValueError):
        Settings(min_score=2)
    with pytest.raises(ValueError):
        Settings(min_hand_scale=.7, max_hand_scale=.6)
    engine = make()
    observe(engine, 1)
    with pytest.raises(ValueError, match="monotonic"):
        observe(engine, .9)
    with pytest.raises(ValueError):
        engine.tick(math.nan)


def test_simulation_rejects_invalid_operations():
    factory = Factory()
    assert not factory.command("pause")[0]
    assert not factory.command("start", "missing")[0]
    with pytest.raises(ValueError):
        factory.select(3)
    with pytest.raises(ValueError):
        factory.set_speed(101)
    with pytest.raises(ValueError):
        factory.tick(-1)


def test_mode_change_clears_pending_and_relocks():
    engine = make()
    unlock(engine)
    preview(engine)
    engine.set_mode("protected")
    assert engine.state == State.LOCKED
    assert engine.pending is None
    assert not engine.unlocked


def test_confirmation_hold_must_be_continuous():
    engine = make()
    unlock(engine)
    preview(engine)
    observe(engine, 3, "Pinch")
    observe(engine, 3.3, "Thumb_Up")
    observe(engine, 3.4, "Pinch")
    observe(engine, 3.8, "Pinch")
    assert engine.pending is not None
    assert not events(engine, "command_executed")
    observe(engine, 3.9, "Pinch")
    assert engine.factory.stations[0].state == "running"


def test_ambiguity_during_confirmation_cancels_pending():
    engine = make()
    unlock(engine)
    preview(engine)
    observe(engine, 3, "Pinch", ambiguous=True)
    assert engine.pending is None
    assert engine.state == State.REJECTED
    assert engine.factory.stations[0].state == "stopped"


def test_nonfinite_model_measurement_is_rejected_without_invalid_json():
    engine = make()
    observe(engine, 1, "Thumb_Up", score=math.nan)
    assert "Non-finite" in engine.reason
    assert json.dumps(engine.snapshot(), allow_nan=False)


def test_manual_target_selects_station_before_preview():
    engine = make()
    assert engine.manual("start", "inspection")[0]
    assert engine.factory.selected == 2
    assert engine.manual("confirm")[0]
    assert engine.factory.station("inspection").state == "running"
    assert engine.factory.station("ventilation").state == "stopped"


def test_event_query_excludes_raw_samples_before_applying_limit():
    store = EventStore()
    operational = store.append({"type": "command_executed", "message": "Start committed."})
    for _ in range(100):
        store.append({"type": "input_observation"})
    store.append({"type": "performance_sample"})
    store.append({"type": "state_changed"})
    result = store.query(limit=20, exclude_types=["input_observation", "performance_sample", "state_changed"])
    assert result == [operational]
    assert len(store.query(limit=3, exclude_types=[])) == 3
    assert store.query(exclude_types=["command_executed' OR 1=1 --"], limit=1)[0]["type"] == "state_changed"
    with pytest.raises(ValueError):
        store.query(exclude_types="input_observation")
    store.close()
