"""HTTP / WebSocket integration tests with no real camera or background clock."""
import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from gestureguard import api
from gestureguard.domain import Observation
from gestureguard.runtime import Runtime


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path, start_worker=False)
    monkeypatch.setattr(api, "Runtime", lambda data_dir=None: runtime)
    with TestClient(api.create_app(tmp_path)) as client:
        yield client, runtime


def test_http_manual_lifecycle_without_camera(local_app):
    client, runtime = local_app
    response = client.post("/api/control", json={"action": "start"})
    assert response.status_code == 200 and response.json()["ok"]
    snapshot = client.get("/api/snapshot").json()
    assert snapshot["engine"]["state"] == "AWAITING_CONFIRMATION"
    assert snapshot["stations"][0]["state"] == "stopped"
    runtime._update(time.monotonic())
    assert runtime.engine.pending is not None
    assert client.post("/api/control", json={"action": "confirm"}).json()["ok"]
    assert client.get("/api/snapshot").json()["stations"][0]["state"] == "running"
    runtime.factory.tick(2)
    assert runtime.factory.stations[0].rpm > 0
    assert client.post("/api/control", json={"action": "stop"}).json()["ok"]
    assert runtime.factory.stations[0].rpm == 0
    assert runtime.store.query(type="command_executed")[0]["details"]["source"] == "manual"


def test_http_invalid_context_does_not_change_factory(local_app):
    client, runtime = local_app
    result = client.post("/api/control", json={"action": "pause"})
    assert result.status_code == 200 and result.json()["ok"] is False
    assert "pause requires a running station" in result.json()["message"]
    assert runtime.factory.stations[0].state == "stopped"
    assert not runtime.engine.pending


@pytest.mark.parametrize("settings", [{"min_score": 2}, {"hold_seconds": 0}, {"unknown": .5}, {"min_hand_scale": .8, "max_hand_scale": .2}])
def test_invalid_settings_are_rejected_atomically(local_app, settings):
    client, runtime = local_app
    before = runtime.settings.to_dict()
    response = client.post("/api/settings", json=settings)
    assert response.status_code == 400
    assert runtime.settings.to_dict() == before
    assert not (runtime.data_dir / "settings.json").exists()


def test_valid_settings_save_and_cancel_pending(local_app):
    client, runtime = local_app
    client.post("/api/control", json={"action": "start"})
    response = client.post("/api/settings", json={"hold_seconds": .9})
    assert response.status_code == 200
    assert runtime.settings.hold_seconds == .9
    assert runtime.engine.pending is None
    assert runtime.engine.snapshot()["state"] == "LOCKED"
    assert json.loads((runtime.data_dir / "settings.json").read_text())["hold_seconds"] == .9


def test_cross_origin_http_and_websocket_are_rejected(local_app):
    client, runtime = local_app
    blocked = client.post("/api/control", json={"action": "start"}, headers={"Origin": "https://untrusted.example"})
    assert blocked.status_code == 403
    assert runtime.engine.pending is None
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/ws", headers={"Origin": "https://untrusted.example"}):
            pass
    assert error.value.code == 1008


def test_websocket_snapshot_and_allowed_origin(local_app):
    client, runtime = local_app
    with client.websocket_connect("/ws", headers={"Origin": "http://127.0.0.1:8765"}) as socket:
        payload = socket.receive_json()
        assert payload["engine"]["state"] == "LOCKED"
        assert len(payload["stations"]) == 3
        assert payload["vision"]["source"] == "simulated"
    assert client.get("/api/health").json()["local_only"] is True


def test_camera_failure_state_and_no_camera_bytes_in_simulation(local_app):
    client, runtime = local_app
    response = client.get("/api/camera/frame")
    assert response.status_code == 503
    assert "No live camera frame" in response.json()["detail"]
    assert runtime.vision.snapshot()["status"] == "idle"


def test_replay_source_blocks_gesture_injection(local_app):
    client, runtime = local_app
    response = client.post("/api/source", json={"source": "replay"})
    assert response.status_code == 200
    assert runtime.source == "replay"
    assert runtime.engine.snapshot()["state"] == "LOCKED"
    assert client.post("/api/input", json={"gesture": "Thumb_Up"}).status_code == 400
    runtime._update(time.monotonic())
    assert runtime._last_observation.source == "replay"
    assert runtime.store.query(type="input_observation")[0]["details"]["source"] == "replay"


def test_replay_export_import_has_honest_source(local_app):
    client, runtime = local_app
    assert client.post("/api/input", json={"gesture": "ILoveYou"}).status_code == 200
    runtime._update(time.monotonic())
    export = client.get("/api/replay/export").json()
    assert export["kind"] == "recorded_observations"
    assert export["observations"][0]["source"] == "simulated"
    assert client.post("/api/replay", json=export).status_code == 200
    runtime._update(time.monotonic())
    assert runtime._last_observation.source == "replay"
    assert runtime.source == "replay"


def test_audit_csv_and_json_exports_are_real_events(local_app):
    client, runtime = local_app
    client.post("/api/control", json={"action": "start"})
    client.post("/api/control", json={"action": "confirm"})
    exported = client.get("/api/export?format=json").json()
    assert any(row["type"] == "command_executed" for row in exported)
    csv = client.get("/api/export?format=csv")
    assert csv.status_code == 200 and "text/csv" in csv.headers["content-type"]
    assert "command_executed" in csv.text
    assert client.get("/api/export?format=xml").status_code == 400


def test_session_filters_and_annotations(local_app):
    client, runtime = local_app
    session = client.post("/api/session", json={"operator_id": "P07", "lighting": "dim", "distance": "near", "glove": "none"}).json()
    client.post("/api/control", json={"action": "start"})
    client.post("/api/control", json={"action": "confirm"})
    event = runtime.store.query(type="command_executed")[0]
    annotation = client.post("/api/annotation", json={"type": "command_label", "event_id": event["id"], "intended": False})
    assert annotation.status_code == 200
    summary = client.get("/api/evaluation?operator_id=P07&lighting=dim").json()
    metrics = {metric["key"]: metric["value"] for metric in summary["metrics"]}
    assert metrics["unintended_activations"] == 1
    assert session["id"] in summary["sessions"]
    assert client.post("/api/annotation", json={"type": "command_label", "event_id": -1, "intended": False}).status_code == 400


class FakeVision:
    def __init__(self):
        self.observation = None
        self.starts = self.stops = 0

    def latest(self):
        return self.observation

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1

    def snapshot(self):
        return {"status": "streaming", "source": "live", "fps": 12, "recognition_ms": 25, "frame_age_ms": 50, "hands": 1, "landmarks": [], "error": None, "hand_scale": .2}


def test_runtime_never_accumulates_hold_from_duplicate_or_stale_live_frame(tmp_path):
    runtime = Runtime(tmp_path, start_worker=False)
    vision = FakeVision()
    runtime.vision = vision
    try:
        runtime.set_source("live")
        now = time.monotonic()
        vision.observation = Observation(now, "ILoveYou", .99, 1, source="live")
        runtime._update(now)
        runtime._update(now + .3)
        assert runtime.engine.hold_progress == 0
        runtime._update(now + .8)
        assert runtime._last_observation.hands == 0
        assert runtime.engine.snapshot()["state"] == "LOCKED"
        vision.observation = Observation(now + .9, "ILoveYou", .99, 1, source="live")
        runtime._update(now + .9)
        assert runtime.engine.hold_progress == 0
        assert runtime.engine.unlocked is False
    finally:
        runtime.close()


def test_api_replay_stops_live_capture_before_switching(local_app):
    client, runtime = local_app
    vision = FakeVision()
    runtime.vision = vision
    assert client.post("/api/source", json={"source": "live"}).status_code == 200
    assert vision.starts == 1
    payload = {"observations": [{"gesture": "None", "duration": 1, "hands": 0}]}
    assert client.post("/api/replay", json=payload).status_code == 200
    assert vision.stops == 1
    assert runtime.source == "replay"


def test_unknown_host_and_invalid_input_shape_are_rejected(local_app):
    client, runtime = local_app
    assert client.get("/api/snapshot", headers={"Host": "attacker.example"}).status_code == 400
    assert client.post("/api/input", json={"gesture": "Thumb_Up", "duration": -1}).status_code == 422
    assert client.post("/api/input", json={"gesture": "Thumb_Up", "source": "live"}).status_code == 422
    assert client.post("/api/input", json={"gesture": "unknown"}).status_code == 400


@pytest.mark.parametrize("payload", [
    {"observations": "invalid"},
    {"observations": ["invalid"]},
    {"events": [{"type": "input_observation", "details": "invalid"}]},
    {"observations": [{"gesture": "Thumb_Up", "score": 2}]},
    {"observations": [{"gesture": "Thumb_Up", "hands": 3}]},
    {"observations": [{"gesture": "Thumb_Up", "hands": True}]},
    {"observations": [{"gesture": "Thumb_Up", "duration": -1}]},
    {"observations": [{"gesture": "Thumb_Up", "timestamp": 1}, {"gesture": "None"}]},
    {"observations": [{"gesture": "Thumb_Up", "timestamp": 1}, {"gesture": "None", "timestamp": .5}]},
    {"observations": [{"gesture": {"name": "Thumb_Up"}}]},
    {"kind": 17, "observations": [{"gesture": "None"}]},
])
def test_invalid_replay_is_rejected_without_mutating_current_preview(local_app, payload):
    client, runtime = local_app
    client.post("/api/control", json={"action": "start"})
    pending = dict(runtime.engine.pending)
    response = client.post("/api/replay", json=payload)
    assert response.status_code == 400
    assert runtime.source == "simulated"
    assert runtime.engine.pending == pending


def test_direct_runtime_replay_stops_capture_and_removes_held_input(tmp_path):
    runtime = Runtime(tmp_path, start_worker=False)
    vision = FakeVision()
    runtime.vision = vision
    try:
        runtime.set_source("live")
        runtime.load_replay({"observations": [{"gesture": "None", "duration": 1, "hands": 0}]})
        assert vision.stops == 1
        assert runtime.source == "replay"
        assert runtime._input is None
    finally:
        runtime.close()


def test_operational_snapshot_never_aggregates_full_history(tmp_path, monkeypatch):
    """A growing audit database must not stall command holds through WS snapshots."""
    runtime = Runtime(tmp_path, start_worker=False)
    original = runtime.store.query
    requested = []
    def bounded_query(limit=200, **filters):
        requested.append(limit)
        assert limit <= 60
        return original(limit=limit, **filters)
    monkeypatch.setattr(runtime.store, "query", bounded_query)
    try:
        assert runtime.snapshot()["engine"]["state"] == "LOCKED"
        assert requested == [20]
    finally:
        runtime.close()


def test_html_revalidates_after_a_frontend_build(local_app):
    client, _ = local_app
    assert client.get("/").headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("mode,expected_state", [
    ("baseline", "running"),
    ("protected", "stopped"),
    ("gestureguard", "stopped"),
])
def test_same_accidental_scenario_preserves_mode_and_demonstrates_guards(tmp_path, mode, expected_state):
    runtime = Runtime(tmp_path, start_worker=False)
    try:
        runtime.engine.set_mode(mode)
        runtime.scenario("locked")
        assert runtime.engine.mode == mode
        started = runtime._step_started
        for frame in range(18):
            runtime._update(started + frame * .05)
        assert runtime.factory.stations[0].state == expected_state
        assert runtime.engine.mode == mode
        assert all(event["mode"] == mode for event in runtime.store.query(type="command_executed"))
        if mode != "baseline":
            assert runtime.engine.snapshot()["state"] == "LOCKED"
            assert runtime.store.query(type="rejected")
    finally:
        runtime.close()


def test_worker_samples_timestamp_after_acquiring_command_lock(tmp_path, monkeypatch):
    """Reproduce an HTTP time advance at lock acquisition without timing sleeps."""
    from threading import RLock
    from types import SimpleNamespace
    import gestureguard.runtime as runtime_module

    runtime = Runtime(tmp_path, start_worker=False)
    clock = {"now": 10.0}
    monkeypatch.setattr(runtime_module, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
    original_update = runtime._update

    class HttpAdvanceAtAcquisition:
        def __init__(self):
            self.lock = RLock()
            self.advanced = False

        def __enter__(self):
            self.lock.acquire()
            if not self.advanced:
                self.advanced = True
                # Simulates an HTTP control that advanced engine time while the
                # worker waited for this shared command lock.
                clock["now"] = 20.0
                runtime.engine.tick(20.0)
            return self

        def __exit__(self, *_):
            self.lock.release()

    def update_then_stop(now):
        original_update(now)
        runtime._stop.set()

    runtime._lock = HttpAdvanceAtAcquisition()
    runtime._update = update_then_stop
    try:
        runtime._run()
        assert runtime.engine.now == 20
        assert runtime._last_observation.timestamp == 20
        assert runtime.store.query(type="runtime_error") == []
    finally:
        runtime.close()
