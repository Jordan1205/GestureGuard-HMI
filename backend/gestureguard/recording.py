"""Voluntary, local-only human landmark collection and conservative calibration.

This module never synthesizes a human sample and never enables a custom model.
Recording I/O runs outside the command/UI workers. Optional camera images need
separate consent; landmarks alone are the default research artifact.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from threading import Event, RLock, Thread, current_thread
import time
from typing import Callable
from uuid import uuid4

from .domain import GESTURES

LABELS = GESTURES | {"Negative"}


class RecordingService:
    def __init__(self, directory: Path):
        self.directory = directory
        self._lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._active = False
        self._started = 0.0
        self._duration = 0.0
        self._id = None
        self._label = None
        self._samples = self._usable = 0
        self._save_images = False
        self._message = "Not recording. Camera data is saved only after explicit consent."
        self._manifest: dict = {}
        self._completed = self._dataset_samples = 0
        if directory.exists():
            for manifest in directory.glob("*/manifest.json"):
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    self._completed += 1
                    self._dataset_samples += int(data.get("samples", 0))
                except (OSError, ValueError, TypeError):
                    continue

    @property
    def active(self):
        with self._lock:
            return self._active

    def start(self, *, consent: bool, label: str, duration_seconds: float,
              save_images: bool, session: dict, settings: dict,
              provider: Callable[[], dict | None]):
        if consent is not True:
            raise ValueError("Consent is required for every local recording.")
        if label not in LABELS or not math.isfinite(duration_seconds) or not 3 <= duration_seconds <= 60:
            raise ValueError("Choose a supported label and a duration of 3–60 seconds.")
        with self._lock:
            if self._active or (self._thread and self._thread.is_alive()):
                raise ValueError("Stop the active recording before starting another.")
            self._id, self._label = str(uuid4()), label
            self._started, self._duration = time.monotonic(), duration_seconds
            self._samples = self._usable = 0
            self._save_images = save_images
            self._stop.clear()
            self._active = True
            self._message = "Recording real webcam observations locally. Command interaction is locked."
            self._manifest = {"recording_id": self._id, "participant_id": session["operator_id"],
                "session_id": session["id"], "conditions": {k: session[k] for k in ("lighting", "distance", "glove")},
                "label": label, "origin": "real_webcam", "source": "live", "consent": True,
                "save_images": save_images, "settings": settings, "model": "MediaPipe GestureRecognizer v1",
                "created_at": datetime.now(timezone.utc).isoformat(), "samples": 0, "usable_samples": 0,
                "status": "recording", "requested_seconds": duration_seconds}
            target = self.directory / self._id
            target.mkdir(parents=True, exist_ok=False)
            self._write_manifest(target)
            self._thread = Thread(target=self._collect, args=(target, provider), name="voluntary-recorder", daemon=True)
            self._thread.start()

    def _write_manifest(self, target: Path):
        temporary = target / "manifest.tmp"
        temporary.write_text(json.dumps(self._manifest, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(target / "manifest.json")

    def _collect(self, target: Path, provider):
        last_capture = -1.0
        first_capture = None
        try:
            with (target / "samples.jsonl").open("w", encoding="utf-8") as output:
                while not self._stop.is_set() and time.monotonic() - self._started < self._duration:
                    sample = provider()
                    if sample is not None:
                        captured = float(sample.get("captured_at", -1))
                        if math.isfinite(captured) and captured > last_capture:
                            last_capture = captured
                            first_capture = captured if first_capture is None else first_capture
                            jpeg = sample.pop("jpeg", None)
                            row = {**sample, "timestamp": captured - first_capture,
                                   "expected": self._label, "source": "live", "origin": "real_webcam"}
                            output.write(json.dumps(row, allow_nan=False) + "\n")
                            output.flush()
                            with self._lock:
                                self._samples += 1
                                if row.get("hands") == 1 and len(row.get("landmarks", [])) == 21:
                                    self._usable += 1
                                count = self._samples
                            if self._save_images and jpeg:
                                images = target / "images"
                                images.mkdir(exist_ok=True)
                                (images / f"{count:05d}.jpg").write_bytes(jpeg)
                    self._stop.wait(.1)
            message = "Recording saved locally." if self._samples else "No fresh camera samples collected; no human data available."
        except Exception as exc:
            message = f"Recording stopped: {exc}"
        finally:
            with self._lock:
                self._active = False
                self._message = message
                self._manifest.update(samples=self._samples, usable_samples=self._usable,
                    elapsed_seconds=round(min(time.monotonic()-self._started,self._duration),3), status="completed")
                self._write_manifest(target)
                self._completed += 1
                self._dataset_samples += self._samples

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread and thread is not current_thread():
            thread.join(timeout=5)

    def snapshot(self, camera_ready=False):
        with self._lock:
            elapsed = min(time.monotonic()-self._started,self._duration) if self._started else 0
            return {"active": self._active, "recording_id": self._id, "label": self._label,
                    "elapsed_seconds": round(elapsed,2), "duration_seconds": self._duration,
                    "progress": min(1,elapsed/self._duration) if self._duration else 0,
                    "samples": self._samples, "usable_samples": self._usable,
                    "completed_recordings": self._completed, "dataset_samples": self._dataset_samples,
                    "camera_ready": camera_ready, "message": self._message, "save_images": self._save_images}


def calibration_report(directory: Path) -> dict:
    """Suggest thresholds only from matching positives plus labeled negatives.

    These are calibration-set summaries, never held-out accuracy estimates. A
    threshold change is withheld if insufficient data or observed confusion would
    make it unsupported. Applying a suggestion is a separate explicit operation.
    """
    rows, fingerprints = [], []
    recordings = 0
    if directory.exists():
        for manifest_path in sorted(directory.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("origin") != "real_webcam" or manifest.get("status") != "completed":
                    continue
                path = manifest_path.parent/"samples.jsonl"
                content = path.read_bytes()
                fingerprints.append((manifest.get("recording_id"),hashlib.sha256(content).hexdigest()))
                recordings += 1
                for line in content.decode("utf-8").splitlines():
                    row = json.loads(line)
                    if row.get("origin") == "real_webcam" and row.get("source") == "live":
                        rows.append({**row,"recording_id":manifest.get("recording_id")})
            except (OSError, ValueError, TypeError):
                continue
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("expected","Negative")].append(row)
    suggestions, summary = {}, []
    warnings = ["Calibration summaries use collected samples, not independent test data.",
                "Threshold suggestions require repeated labeled positives and negative examples; they never change settings automatically."]
    def score(row):
        value = row.get("score",row.get("raw_score",0))
        return float(value) if isinstance(value,(int,float)) and math.isfinite(value) else 0.0
    for gesture, examples in sorted(grouped.items()):
        predicted = lambda row: row.get("gesture",row.get("raw_gesture","None"))
        correct = [row for row in examples if predicted(row) == gesture and row.get("hands") == 1]
        scores = sorted(score(row) for row in correct)
        p10 = scores[int((len(scores)-1)*.1)] if scores else None
        agreement = len(correct)/len(examples) if examples else None
        negatives = [row for row in rows if row.get("expected") in {"None","Negative"} and row.get("hands")==1]
        distinct = {row["recording_id"] for row in correct}
        suggested = None
        note = "Collect at least 20 matching positive samples over two clips and 20 neutral/negative samples."
        if gesture == "Pinch":
            note = "Pinch uses an explicit normalized fingertip-distance gate, not the classifier score threshold. Review geometry diagnostics."
        if gesture in GESTURES-{"None","Pinch"} and len(correct)>=20 and len(distinct)>=2 and len(negatives)>=20:
            candidate = round(max(.55,min(.9,p10-.03)),2)
            false_positives = [row for row in negatives if predicted(row)==gesture and score(row)>=candidate]
            if agreement >= .7 and not false_positives:
                suggested = candidate
                suggestions[gesture] = candidate
                note = "Provisional positive/negative calibration suggestion. Validate on a separate session before evaluating."
            else:
                note = "Observed confusion/negative matches: improve pose or collect more data; lowering a threshold is not justified."
        summary.append({"gesture":gesture,"samples":len(examples),"correct_samples":len(correct),
                        "agreement":round(agreement,3),"raw_score_median":median([float(r.get("raw_score",r.get("score",0))) for r in examples]),
                        "raw_score_p10":p10,"threshold_suggestion":suggested,"note":note})
    report_id = hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest()[:20]
    return {"report_id":report_id,"recordings":recordings,"samples":len(rows),"by_gesture":summary,
            "suggestions":{"gesture_thresholds":suggestions},"can_apply":bool(suggestions),"warnings":warnings,
            "source":"local_real_webcam","status":"ready" if rows else "No real webcam recordings collected yet."}
