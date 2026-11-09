"""Synthetic unit fixtures exercise storage, never represent collected human data."""
import json
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

from gestureguard.api import create_app
from gestureguard.recording import RecordingService, calibration_report

SESSION={"id":"session-test","operator_id":"test-operator","lighting":"normal","distance":"comfortable","glove":"none"}


def test_recording_requires_voluntary_consent_without_creating_files(tmp_path):
    recorder=RecordingService(tmp_path/"recordings")
    with pytest.raises(ValueError,match="Consent"):
        recorder.start(consent=False,label="Thumb_Up",duration_seconds=3,save_images=False,
            session=SESSION,settings={},provider=lambda:None)
    assert not (tmp_path/"recordings").exists()


def test_opt_in_worker_deduplicates_fresh_samples_and_omits_images(tmp_path):
    recorder=RecordingService(tmp_path/"recordings")
    sample={"captured_at":10.0,"hands":1,"landmarks":[[0,0,0]]*21,
            "gesture":"Thumb_Up","raw_gesture":"Thumb_Up","score":.61,"raw_score":.61,"jpeg":b"image"}
    recorder.start(consent=True,label="Thumb_Up",duration_seconds=3,save_images=False,
        session=SESSION,settings={},provider=lambda:dict(sample))
    deadline=time.monotonic()+2
    while recorder.snapshot()["samples"]==0 and time.monotonic()<deadline:
        time.sleep(.01)
    recorder.stop()
    status=recorder.snapshot()
    assert not status["active"] and status["samples"]==status["usable_samples"]==1
    folder=tmp_path/"recordings"/status["recording_id"]
    row=json.loads((folder/"samples.jsonl").read_text())
    assert row["expected"]=="Thumb_Up" and row["origin"]=="real_webcam" and "jpeg" not in row
    assert row["raw_score"]==.61
    assert not (folder/"images").exists()
    manifest=json.loads((folder/"manifest.json").read_text())
    assert manifest["consent"] and manifest["participant_id"]=="test-operator"
    assert RecordingService(tmp_path/"recordings").snapshot()["dataset_samples"]==1


def test_no_camera_samples_yields_an_honest_empty_recording(tmp_path):
    recorder=RecordingService(tmp_path)
    recorder.start(consent=True,label="Negative",duration_seconds=3,save_images=False,
        session=SESSION,settings={},provider=lambda:None)
    recorder.stop()
    assert recorder.snapshot()["samples"]==0
    assert "No fresh camera samples" in recorder.snapshot()["message"]
    assert calibration_report(tmp_path)["samples"]==0


def test_calibration_without_real_recordings_has_no_suggestions(tmp_path):
    report=calibration_report(tmp_path)
    assert report["samples"]==report["recordings"]==0
    assert not report["can_apply"] and report["suggestions"]["gesture_thresholds"]=={}


def write_calibration_fixture(path: Path,label,gesture,score,recording_id):
    folder=path/recording_id
    folder.mkdir()
    (folder/"manifest.json").write_text(json.dumps({"origin":"real_webcam","status":"completed","recording_id":recording_id}))
    (folder/"samples.jsonl").write_text("\n".join(json.dumps({"origin":"real_webcam","source":"live","expected":label,
        "gesture":gesture,"raw_gesture":gesture,"score":score,"raw_score":score,"hands":1}) for _ in range(20)))


def test_calibration_requires_repetition_and_checked_negative_examples(tmp_path):
    write_calibration_fixture(tmp_path,"Thumb_Up","Thumb_Up",.62,"positive1")
    assert not calibration_report(tmp_path)["can_apply"]
    write_calibration_fixture(tmp_path,"Thumb_Up","Thumb_Up",.62,"positive2")
    assert not calibration_report(tmp_path)["can_apply"]
    write_calibration_fixture(tmp_path,"Negative","None",.8,"negative")
    report=calibration_report(tmp_path)
    assert report["can_apply"] and report["suggestions"]["gesture_thresholds"]["Thumb_Up"]==.59
    write_calibration_fixture(tmp_path,"Negative","Thumb_Up",.8,"falsepositive")
    assert not calibration_report(tmp_path)["can_apply"]


def test_http_recording_refuses_simulated_data_and_calibration_is_opt_in(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/recording").json()["camera_ready"] is False
        result=client.post("/api/recording/start",json={"consent":True,"label":"Thumb_Up","duration_seconds":3})
        assert result.status_code==400 and "Live Camera" in result.json()["detail"]
        report=client.get("/api/calibration").json()
        assert report["samples"]==0
        assert client.post("/api/calibration/apply",json={"consent":False,"report_id":report["report_id"]}).status_code==400
        assert client.post("/api/calibration/apply",json={"consent":True,"report_id":report["report_id"]}).status_code==400
        assert client.post("/api/recording/stop",json={}).status_code==200


def test_mixed_settings_body_accepts_activation_configuration(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response=client.post("/api/settings",json={"easy_demo":False,"activation_gesture":"ILoveYou","gesture_thresholds":{"Thumb_Up":.63}})
        assert response.status_code==200
        settings=client.get("/api/snapshot").json()["engine"]["settings"]
        assert settings["activation_gesture"]=="ILoveYou" and settings["gesture_thresholds"]["Thumb_Up"]==.63


def test_recording_locks_consequential_manual_actions(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        runtime=client.app.state.runtime
        runtime.recorder._active=True
        assert client.post("/api/control",json={"action":"start"}).status_code==400
        assert client.post("/api/control",json={"action":"confirm"}).status_code==400
        assert runtime.factory.stations[0].state=="stopped"
        assert client.post("/api/control",json={"action":"stop"}).status_code==200
        runtime.recorder._active=False


def test_camera_recording_images_are_opt_in_original_frames(tmp_path):
    import numpy as np
    import cv2
    from gestureguard.domain import Observation, Settings
    from gestureguard.vision import VisionService
    vision=VisionService(tmp_path/"unused.task",Settings())
    vision._status="streaming"
    vision._observation=Observation(time.monotonic(),"Open_Palm",.8,1,source="live")
    vision._landmarks=[[[0,0,0]]*21]
    vision._recording_frame=np.zeros((40,60,3),dtype=np.uint8)
    vision._jpeg=b"annotated UI image is not a training artifact"
    assert "jpeg" not in vision.recording_sample()
    sample=vision.recording_sample(include_images=True)
    decoded=cv2.imdecode(np.frombuffer(sample["jpeg"],dtype=np.uint8),cv2.IMREAD_COLOR)
    assert decoded.shape==(40,60,3)
    assert sample["jpeg"]!=vision._jpeg


def test_stale_inference_is_not_reported_as_a_current_hand(tmp_path):
    from gestureguard.domain import Observation, Settings
    from gestureguard.vision import VisionService
    vision=VisionService(tmp_path/"unused.task",Settings())
    vision._status="streaming"
    vision._frame_time=time.monotonic()
    vision._observation=Observation(time.monotonic()-1,"Open_Palm",.9,1,source="live")
    vision._landmarks=[[[0,0,0]]*21]
    snapshot=vision.snapshot()
    assert snapshot["frame_age_ms"]<100
    assert snapshot["inference_age_ms"]>900
    assert snapshot["hands"]==0 and snapshot["landmarks"]==[]
    assert vision.recording_sample() is None
