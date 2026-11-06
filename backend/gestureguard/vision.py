"""Latest-frame capture and inference workers, independent of ASGI/UI loops."""
from __future__ import annotations

from collections import deque
from pathlib import Path
from threading import Event, Lock, Thread
import time

from .domain import Settings
from .gesture_recognition import HAND_CONNECTIONS, interpret_result


class VisionService:
    def __init__(self, model_path: Path, settings: Settings, camera_index: int = 0):
        self.model_path, self.settings, self.camera_index = model_path, settings, camera_index
        self._lock = Lock()
        self._stop = Event()
        self._threads: list[Thread] = []
        self._frame = None
        self._frame_number = 0
        self._frame_time = 0.0
        self._observation = None
        self._landmarks = []
        self._jpeg: bytes | None = None
        self._status = "idle"
        self._error: str | None = None
        self._fps = 0.0
        self._recognition_ms = 0.0

    def start(self):
        if any(t.is_alive() for t in self._threads):
            raise ValueError("Camera workers are still stopping. Retry in a moment.")
        if not self.model_path.exists():
            raise ValueError("Gesture model is missing. Run scripts/download_model.py first.")
        self._stop.clear()
        with self._lock:
            self._frame = self._observation = self._jpeg = None
            self._landmarks = []
            self._status, self._error = "starting", None
        self._threads = [Thread(target=self._capture, name="camera-capture", daemon=True),
                         Thread(target=self._infer, name="gesture-inference", daemon=True)]
        for thread in self._threads:
            thread.start()

    def stop(self):
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=3)
        with self._lock:
            self._status = "idle"
            self._observation = self._jpeg = None
            self._landmarks = []
            self._fps = 0

    def _fail(self, message: str):
        with self._lock:
            self._status, self._error = "unavailable", message
            self._observation = self._jpeg = None
        self._stop.set()

    def _capture(self):
        cap = None
        try:
            import cv2
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                raise RuntimeError("Cannot open webcam. Check Windows camera permission and close other camera apps.")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("Webcam stopped returning frames. Reconnect it and select Live Camera again.")
                with self._lock:
                    self._frame = cv2.flip(frame, 1)
                    self._frame_number += 1
                    self._frame_time = time.monotonic()
                self._stop.wait(.005)
        except Exception as exc:
            self._fail(str(exc))
        finally:
            if cap is not None:
                cap.release()

    def _infer(self):
        recognizer = None
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            options = vision.GestureRecognizerOptions(
                base_options=python.BaseOptions(model_asset_path=str(self.model_path)),
                running_mode=vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.5, min_hand_presence_confidence=.5,
                min_tracking_confidence=.5)
            recognizer = vision.GestureRecognizer.create_from_options(options)
            previous_frame, previous_ms = -1, -1
            times = deque(maxlen=45)
            while not self._stop.is_set():
                with self._lock:
                    number, frame, captured = self._frame_number, self._frame, self._frame_time
                if frame is None or number == previous_frame:
                    self._stop.wait(.01)
                    continue
                previous_frame = number
                timestamp_ms = max(previous_ms + 1, int(captured * 1000))
                previous_ms = timestamp_ms
                started = time.perf_counter()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = recognizer.recognize_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
                elapsed_ms = (time.perf_counter() - started)*1000
                observation, landmarks = interpret_result(result, captured, elapsed_ms, self.settings,
                                                          frame.shape[1]/frame.shape[0])
                annotated = frame.copy()
                height, width = frame.shape[:2]
                for hand in landmarks:
                    for a, b in HAND_CONNECTIONS:
                        pa, pb = hand[a], hand[b]
                        cv2.line(annotated, (int(pa[0]*width), int(pa[1]*height)),
                                 (int(pb[0]*width), int(pb[1]*height)), (180,210,60), 2)
                    for point in hand:
                        cv2.circle(annotated, (int(point[0]*width),int(point[1]*height)), 3, (230,245,220), -1)
                cv2.putText(annotated, f"LIVE CAMERA | {observation.gesture} | hands {observation.hands}",
                            (14,28), cv2.FONT_HERSHEY_SIMPLEX, .55, (220,240,220), 1, cv2.LINE_AA)
                ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 78])
                now = time.monotonic()
                times.append(now)
                fps = (len(times)-1)/(times[-1]-times[0]) if len(times)>1 else 0.0
                with self._lock:
                    if self._stop.is_set():
                        break
                    self._observation, self._landmarks = observation, landmarks
                    self._jpeg = encoded.tobytes() if ok else None
                    self._status, self._error = "streaming", None
                    self._fps, self._recognition_ms = fps, elapsed_ms
                self._stop.wait(.005)
        except Exception as exc:
            self._fail(f"Vision unavailable: {exc}")
        finally:
            if recognizer is not None:
                recognizer.close()

    def latest(self):
        with self._lock:
            return self._observation

    def jpeg(self):
        with self._lock:
            return self._jpeg

    def snapshot(self):
        with self._lock:
            age = (time.monotonic()-self._frame_time)*1000 if self._frame_time else None
            return {"status": self._status, "source": "live", "fps": round(self._fps,1),
                    "recognition_ms": round(self._recognition_ms,2), "frame_age_ms": age,
                    "hands": self._observation.hands if self._observation else 0,
                    "landmarks": self._landmarks, "error": self._error,
                    "hand_scale": self._observation.hand_scale if self._observation else None}
