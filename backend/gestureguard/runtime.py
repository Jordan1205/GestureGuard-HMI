"""Application coordinator. One worker serializes command and simulation updates."""
from __future__ import annotations

from dataclasses import fields, replace
import json
import math
from pathlib import Path
from threading import Event, RLock, Thread
import time
from uuid import uuid4

from .domain import GESTURES, Observation, Settings
from .event_store import EventStore
from .intent_engine import IntentEngine
from .simulation import Factory
from .vision import VisionService

ROOT = Path(__file__).resolve().parents[2]


class SessionStore(EventStore):
    """Persist conditions with every event, even after session metadata changes."""
    session: dict

    def append(self, event):
        record = dict(event)
        record["details"] = {**record.get("details", {}), "session": dict(getattr(self,"session",{}))}
        return super().append(record)


def demonstration_steps(name: str, settings: Settings) -> list[dict]:
    hold, unlock, confirm = settings.hold_seconds+.25, settings.unlock_seconds+.25, settings.confirm_seconds+.25
    def step(gesture, duration, label, **kw):
        return {"gesture":gesture,"duration":duration,"label":label, "hands":1, **kw}
    activation = [step("ILoveYou",unlock,"Hold activation gesture"),step("None",.45,"Release to neutral")]
    preview = [step("Thumb_Up",hold,"Request start — preview only")]
    confirmation = [step("Pinch",confirm,"Separate pinch confirms command"),step("None",settings.cooldown_seconds+.3,"Release and cooldown")]
    cases = {
        "locked":[step("Thumb_Up",hold,"Accidental start while locked — rejected")],
        "accepted":activation + [step("Victory",hold,"Stable selection accepted"),step("None",1,"Release")],
        "ambiguous":activation + [step("Thumb_Up",1.5,"Ambiguous input — rejected",ambiguous=True,score=.48)],
        "confirmation":activation+preview+[step("Thumb_Up",2,"Pending: waiting for a separate pinch")],
        "invalid":activation+[step("Closed_Fist",hold,"Pause a stopped station — invalid command")],
        "success":activation+preview+confirmation,
        "hand_loss":activation+preview+[step("None",settings.absence_lock_seconds+.5,"Hand loss cancels intent and locks",hands=0)],
    }
    if name == "tour":
        # One continuous reproducible story, including invalid-context rejection.
        return (cases["locked"]+[step("None",.5,"Release")]+activation+
                [step("Thumb_Up",1,"Ambiguous candidate",ambiguous=True,score=.4),
                 step("None",.5,"Release after rejection"),
                 step("Closed_Fist",hold,"Pause stopped station — invalid"),
                 step("None",.5,"Release")]+preview+
                [step("Thumb_Up",1,"Preview has not changed the factory")]+confirmation+
                [step("Closed_Fist",hold,"Request pause"),step("Pinch",confirm,"Confirm pause"),
                 step("None",settings.absence_lock_seconds+.5,"Hand loss triggers auto-lock",hands=0)])
    if name not in cases:
        raise ValueError("Unknown scenario.")
    return cases[name]


class Runtime:
    def __init__(self, data_dir: Path | None = None, *, start_worker: bool = True):
        self.data_dir = data_dir or ROOT/"data"
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self._lock = RLock()
        self._stop = Event()
        self._thread = None
        self.session = {"id":str(uuid4()),"operator_id":"operator-01","lighting":"unspecified",
                        "distance":"unspecified","glove":"none"}
        self.store = SessionStore(self.data_dir/"events.sqlite3")
        self.store.session = self.session
        self.settings = Settings()
        settings_file = self.data_dir/"settings.json"
        if settings_file.exists():
            try:
                self.settings = Settings(**json.loads(settings_file.read_text(encoding="utf-8")))
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        self.factory = Factory()
        self.engine = IntentEngine(self.factory,self.store,self.settings,session_id=self.session["id"])
        self.vision = VisionService(ROOT/"models"/"gesture_recognizer.task",self.settings)
        self.source = "simulated"
        self._input = None
        self._input_until = 0.0
        self._steps: list[dict] = []
        self._step_index = 0
        self._step_started = 0.0
        self._scenario_name = ""
        self._last_live = -1.0
        self._last_perf = 0.0
        self._last_observation = Observation(0)
        self._log("session_started","Local session started; camera remains closed.",configuration=self.settings.to_dict())
        if start_worker:
            self._thread = Thread(target=self._run,name="intent-simulation",daemon=True)
            self._thread.start()

    def _log(self, kind, message, **details):
        return self.store.append({"type":kind,"message":message,"mode":self.engine.mode,
            "session_id":self.session["id"],"monotonic":time.monotonic(),
            "details":{"source":self.source,**details}})

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.vision.stop()
        self.store.close()

    def _run(self):
        last = time.monotonic()
        while not self._stop.is_set():
            try:
                with self._lock:
                    # Sample after acquiring the command lock: an HTTP control may
                    # have advanced engine time while this worker was waiting.
                    now = time.monotonic()
                    self.factory.tick(now-last)
                    self._update(now)
                    last = now
            except Exception as exc:
                with self._lock:
                    self.engine.lock(f"Runtime error; controls locked: {exc}")
                    self._log("runtime_error",str(exc))
            self._stop.wait(.05)

    def _update(self, now):
        observation = None
        if self._steps:
            while self._step_index < len(self._steps) and now-self._step_started >= self._steps[self._step_index]["duration"]:
                self._step_started += self._steps[self._step_index]["duration"]
                self._step_index += 1
            if self._step_index >= len(self._steps):
                self._steps = []
                self._log("scenario_completed",f"{self._scenario_name} completed.")
            else:
                step = self._steps[self._step_index]
                observation = Observation(now,step.get("gesture","None"),step.get("score",.99),
                    step.get("hands",1),step.get("ambiguous",False),self.source,
                    metadata={"scripted": step.get("scripted",True),"scenario":self._scenario_name,
                              "original_source":step.get("original_source",self.source)})
        if observation is None:
            if self.source == "live":
                current = self.vision.latest()
                if current is not None and now-current.timestamp < .5:
                    if current.timestamp != self._last_live:
                        self._last_live = current.timestamp
                        observation = replace(current,timestamp=now,metadata={**current.metadata,
                            "captured_at":current.timestamp,"capture_to_engine_ms":(now-current.timestamp)*1000})
                else:
                    observation = Observation(now,source="live")
                if now-self._last_perf >= 1 and self.vision.snapshot()["status"] == "streaming":
                    self._last_perf = now
                    self._log("performance_sample","Measured live inference sample.",**self.vision.snapshot())
            elif self.source == "simulated" and self._input and now < self._input_until:
                observation = Observation(now,**self._input)
            else:
                observation = Observation(now,source=self.source)
        if observation:
            # A manual fallback preview remains operable without camera hardware.
            self.engine.process(observation)
            self._last_observation = observation
        else:
            self.engine.tick(now)

    def set_source(self, source):
        if source not in {"live","simulated","replay"}:
            raise ValueError("Source must be live, simulated, or replay.")
        with self._lock:
            if self.source == "live":
                self.vision.stop()
            self.engine.lock("Input source changed; pending action canceled.")
            self.source = source
            self._steps, self._input = [], None
            self._last_live = -1
            self._log("source_changed",f"Input source: {source}.")
            if source == "live":
                self.vision.start()
            elif source == "replay":
                fixture = json.loads((ROOT/"fixtures"/"demo-replay.json").read_text(encoding="utf-8"))
                self.load_replay(fixture)

    def inject(self, payload):
        with self._lock:
            if self.source != "simulated":
                raise ValueError("Injected gestures require Simulated Test Input. Switch the source first.")
            if self._steps:
                raise ValueError("Stop the scenario before injecting a separate gesture.")
            gesture = payload.get("gesture","None")
            score, hands, duration = float(payload.get("score",.99)), int(payload.get("hands",1)), float(payload.get("duration",1.5))
            if gesture not in GESTURES or not 0 <= score <= 1 or not 0 <= hands <= 2 or not .05 <= duration <= 30:
                raise ValueError("Invalid gesture, score, hand count, or duration (0.05–30 seconds).")
            self._input = {"gesture":gesture,"score":score,"hands":hands,
                           "ambiguous":bool(payload.get("ambiguous",False)),"source":"simulated"}
            self._input_until = time.monotonic()+duration

    def scenario(self, name):
        if name == "stop":
            with self._lock:
                self._steps = []
                self._input = None
                self.engine.lock("Scenario stopped; pending action canceled.")
            return
        steps = demonstration_steps(name,self.settings)
        self.set_source("simulated")
        with self._lock:
            self.factory.reset()
            self.engine.manual("reset",timestamp=time.monotonic())
            self._steps,self._step_index,self._step_started = steps,0,time.monotonic()
            self._scenario_name = name
            self._log("scenario_started",f"Scripted scenario: {name}.",scripted=True)

    def load_replay(self, payload):
        """Replay observation records, never classify them as live vision."""
        if not isinstance(payload,dict):
            raise ValueError("Replay must be a JSON object.")
        if not isinstance(payload.get("kind",""),str):
            raise ValueError("Replay kind must be a string.")
        records = payload.get("observations",payload.get("events",[]))
        if not isinstance(records,list) or not records or len(records)>20000:
            raise ValueError("Replay needs 1–20,000 observation records.")
        if any(not isinstance(item,dict) for item in records):
            raise ValueError("Every replay record must be an object.")
        rows = [item.get("details",item) for item in records if item.get("type","input_observation")=="input_observation"]
        if not rows or any(not isinstance(row,dict) for row in rows):
            raise ValueError("No input observations found in this replay.")
        timed=any("timestamp" in row for row in rows)
        if timed and not all(isinstance(row.get("timestamp"),(int,float)) and math.isfinite(row["timestamp"]) for row in rows):
            raise ValueError("All replay timestamps must be finite numbers when timestamps are used.")
        steps=[]
        for i,row in enumerate(rows):
            gesture = row.get("gesture","None")
            if not isinstance(gesture,str) or gesture not in GESTURES:
                raise ValueError("Replay contains an unknown gesture.")
            if not isinstance(row.get("ambiguous",False),bool):
                raise ValueError("Replay ambiguity must be a boolean.")
            try:
                duration = float(row.get("duration",.1))
                score=float(row.get("score",.99))
                hands=row.get("hands",1)
            except (ValueError,TypeError):
                raise ValueError("Replay duration and score must be finite numbers.") from None
            if timed and i+1<len(rows):
                duration = float(rows[i+1]["timestamp"])-float(row["timestamp"])
            if not math.isfinite(duration) or not .001 <= duration <= 60:
                raise ValueError("Replay timestamps must increase; each interval must be <=60 seconds.")
            if not math.isfinite(score) or not 0<=score<=1 or not isinstance(hands,int) or isinstance(hands,bool) or not 0<=hands<=2:
                raise ValueError("Replay score must be 0–1 and hands must be an integer 0–2.")
            steps.append({"gesture":gesture,"score":score,"hands":hands,
                "ambiguous":bool(row.get("ambiguous",False)),"duration":duration,"label":gesture.replace("_"," "),
                "original_source":row.get("source","scripted_fixture"),
                "scripted":payload.get("kind","").startswith("scripted") or row.get("source","simulated")=="simulated"})
        with self._lock:
            if self.source=="live":
                self.vision.stop()
            self.engine.lock("Recorded observation replay started.")
            self.source="replay"
            self._input=None
            self._steps,self._step_index,self._step_started=steps,0,time.monotonic()
            self._scenario_name="Recorded observation replay"
            self._log("replay_started","Recorded observation replay. No camera recognition is being performed.",records=len(rows))

    def update_settings(self, values):
        allowed={field.name for field in fields(Settings)}
        if set(values)-allowed:
            raise ValueError(f"Unknown settings: {', '.join(set(values)-allowed)}")
        validated=Settings(**{**self.settings.to_dict(),**values})
        with self._lock:
            self.settings=validated
            self.engine.settings=validated
            self.vision.settings=validated
            self.engine.lock("Calibration/settings changed; interface locked.")
            (self.data_dir/"settings.json").write_text(json.dumps(validated.to_dict(),indent=2),encoding="utf-8")
            self._log("settings_changed","Validated settings saved.",configuration=validated.to_dict())

    def new_session(self, conditions):
        with self._lock:
            self._steps,self._input=[],None
            self.engine.lock("New evaluation session; interface locked.")
            self.session={"id":str(uuid4()),**{key:str(conditions.get(key,self.session[key]))[:80]
                for key in ("operator_id","lighting","distance","glove")}}
            self.store.session=self.session
            self.engine.session_id=self.session["id"]
            self._log("session_started","Evaluation session started.",configuration=self.settings.to_dict())

    def snapshot(self):
        with self._lock:
            vision=self.vision.snapshot()
            if self.source != "live":
                vision.update(status="simulated" if self.source=="simulated" else "replay",source=self.source,
                    fps=0,recognition_ms=0,frame_age_ms=None,hands=self._last_observation.hands,
                    landmarks=[],error=None,hand_scale=None)
            step=self._steps[self._step_index] if self._steps and self._step_index<len(self._steps) else None
            # Exclude samples before LIMIT, so inactivity cannot erase the timeline.
            timeline=self.store.query(limit=20,exclude_types=["input_observation","performance_sample","state_changed"])
            return {"engine":self.engine.snapshot(),"stations":self.factory.snapshot(),"events":timeline,
                    "vision":vision,"session":dict(self.session),
                    "scenario":{"running":bool(self._steps),"name":self._scenario_name,
                        "step":self._step_index+1 if step else 0,"total":len(self._steps),
                        "label":step["label"] if step else ""}}
