"""Loopback-only HTTP / WebSocket boundary; the Python engine owns commands."""
from contextlib import asynccontextmanager
import asyncio
import csv
import io
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .evaluation import run_comparison, summarize
from .recording import calibration_report
from .runtime import ROOT, Runtime

ALLOWED_ORIGINS = {f"http://{host}:{port}" for host in ("127.0.0.1","localhost") for port in (8765,8766,5173)}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid",allow_inf_nan=False)


class Control(StrictModel):
    action: Literal["start","pause","stop","select","confirm","cancel","lock","reset","speed"]
    station_id: str | None = None
    value: float | int | None = None


class Input(StrictModel):
    gesture: str
    score: float = Field(default=.99,ge=0,le=1)
    hands: int = Field(default=1,ge=0,le=2)
    duration: float = Field(default=1.5,ge=.05,le=30)
    ambiguous: bool = False


class Source(StrictModel):
    source: Literal["live","simulated","replay"]


class Mode(StrictModel):
    mode: Literal["baseline","protected","gestureguard"]


class Scenario(StrictModel):
    name: str


class Session(StrictModel):
    operator_id: str = Field(default="operator-01",max_length=80)
    lighting: str = Field(default="unspecified",max_length=80)
    distance: str = Field(default="unspecified",max_length=80)
    glove: str = Field(default="none",max_length=80)


class Annotation(StrictModel):
    type: Literal["recognition_label","idle_exposure","command_label","task_result"]
    predicted: str | None = None
    expected: str | None = None
    event_id: int | None = None
    intended: bool | None = None
    idle: bool = False
    success: bool | None = None
    duration_seconds: float | None = Field(default=None,gt=0,le=86400)
    gesture: str | None = None


class RecordingStart(StrictModel):
    consent: bool
    label: Literal["ILoveYou","Open_Palm","Closed_Fist","Thumb_Up","Victory","Pointing_Up","Pinch","None","Negative"]
    duration_seconds: float = Field(default=8,ge=3,le=60)
    save_images: bool = False


class CalibrationApply(StrictModel):
    consent: bool
    report_id: str


def create_app(data_dir: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        runtime = Runtime(data_dir)
        app.state.runtime = runtime
        try:
            yield
        finally:
            await asyncio.to_thread(runtime.close)

    app = FastAPI(title="GestureGuard HMI",version="0.1.0",lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","testserver"])

    @app.middleware("http")
    async def local_origin(request: Request,call_next):
        origin=request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return Response("Cross-origin access is disabled.",status_code=403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        if response.headers.get("content-type","").startswith("text/html"):
            response.headers["Cache-Control"]="no-cache"
        return response

    def runtime() -> Runtime:
        return app.state.runtime

    @app.exception_handler(ValueError)
    async def value_error(request,exc):
        return Response(json.dumps({"detail":str(exc)}),status_code=400,media_type="application/json")

    @app.get("/api/health")
    def health():
        return {"status":"ok","application":"GestureGuard HMI","local_only":True}

    @app.get("/api/snapshot")
    def snapshot():
        return runtime().snapshot()

    @app.post("/api/control")
    def control(payload: Control):
        run=runtime()
        with run._lock:
            if run.recorder.active and payload.action not in {"stop","cancel","lock","reset"}:
                raise ValueError("Commands are locked during local recording. Stop recording before controlling a station.")
            if payload.action=="speed":
                if payload.value is None:
                    raise ValueError("Target speed is required.")
                run.factory.set_speed(float(payload.value),payload.station_id)
                run._log("speed_changed","Simulated target speed updated.",station_id=payload.station_id,value=payload.value)
                return {"ok":True,"message":"Target speed updated."}
            target=payload.station_id
            if payload.action=="select" and target is None and payload.value is not None:
                if payload.value != int(payload.value):
                    raise ValueError("Station index must be an integer.")
                target=int(payload.value)
            import time
            ok,message=run.engine.manual(payload.action,target,timestamp=time.monotonic())
            return {"ok":ok,"message":message}

    @app.post("/api/input")
    def inject(payload: Input):
        runtime().inject(payload.model_dump())
        return {"ok":True}

    @app.post("/api/source")
    def source(payload: Source):
        runtime().set_source(payload.source)
        return {"ok":True}

    @app.post("/api/mode")
    def mode(payload: Mode):
        run=runtime()
        with run._lock:
            run._steps,run._input=[],None
            run.engine.set_mode(payload.mode)
        return {"ok":True}

    @app.post("/api/settings")
    def settings(payload: dict[str,Any]):
        runtime().update_settings(payload)
        return {"ok":True,"settings":runtime().settings.to_dict()}

    @app.post("/api/scenario")
    def scenario(payload: Scenario):
        runtime().scenario(payload.name)
        return {"ok":True}

    @app.post("/api/session")
    def session(payload: Session):
        runtime().new_session(payload.model_dump())
        return runtime().session

    @app.get("/api/recording")
    def recording_status():
        run=runtime()
        return run.recorder.snapshot(run.source=="live" and run.vision.snapshot()["status"]=="streaming")

    @app.post("/api/recording/start")
    def recording_start(payload: RecordingStart):
        runtime().start_recording(payload.model_dump())
        return {"ok":True,**recording_status()}

    @app.post("/api/recording/stop")
    def recording_stop():
        runtime().stop_recording()
        return {"ok":True,**recording_status()}

    @app.get("/api/calibration")
    def calibration():
        return calibration_report(runtime().recorder.directory)

    @app.post("/api/calibration/apply")
    def calibration_apply(payload: CalibrationApply):
        runtime().apply_calibration(payload.consent,payload.report_id)
        return {"ok":True,"settings":runtime().settings.to_dict()}

    @app.get("/api/events")
    def events(request: Request):
        filters=dict(request.query_params)
        limit=int(filters.pop("limit",500))
        return runtime().store.query(limit=limit,**filters)

    @app.get("/api/evaluation")
    def evaluation(request: Request):
        return summarize(runtime().store.query(limit=200000),**dict(request.query_params))

    @app.post("/api/evaluation/compare")
    def compare():
        # Independent in-memory factories: never alter the current live session.
        return run_comparison()

    @app.post("/api/annotation")
    def annotate(payload: Annotation):
        details=payload.model_dump(exclude_none=True)
        linked=None
        if payload.type=="recognition_label" and (not payload.predicted or not payload.expected):
            raise ValueError("Recognition labels need expected and predicted gesture.")
        if payload.type in {"idle_exposure","task_result"} and payload.duration_seconds is None:
            raise ValueError("An observed duration in seconds is required.")
        if payload.type=="task_result" and payload.success is None:
            raise ValueError("Task result needs a success label.")
        if payload.type=="command_label":
            if payload.event_id is None or payload.intended is None:
                raise ValueError("A command label needs a recorded event_id and intended true/false.")
            records=runtime().store.query(limit=200000,type="command_executed",session_id=runtime().session["id"])
            linked=next((e for e in records if e["id"]==payload.event_id),None)
            if linked is None:
                raise ValueError("Command event does not exist in this session.")
        run=runtime()
        with run._lock:
            import time
            return run.store.append({"type":payload.type,"message":"Operator-entered evaluation annotation.",
                "mode":linked["mode"] if linked else run.engine.mode,"session_id":run.session["id"],
                "monotonic":time.monotonic(),
                "gesture":linked.get("gesture","None") if linked else (payload.gesture or payload.expected or "None"),
                "details":{"source":linked.get("details",{}).get("source",run.source) if linked else run.source,
                    **{k:v for k,v in details.items() if k!="type"}}})

    def download(records, kind, filename):
        if kind=="json":
            return Response(json.dumps(records,indent=2,allow_nan=False),media_type="application/json",
                            headers={"Content-Disposition":f'attachment; filename="{filename}.json"'})
        if kind!="csv":
            raise ValueError("Export format must be csv or json.")
        buffer=io.StringIO(newline="")
        columns=list(dict.fromkeys(key for row in records for key in row)) if records else ["id","timestamp","type","message"]
        writer=csv.DictWriter(buffer,fieldnames=columns)
        writer.writeheader()
        for row in records:
            # Avoid spreadsheet formula interpretation of operator-entered values.
            safe={key:json.dumps(value) if isinstance(value,(dict,list)) else
                  ("'"+value if isinstance(value,str) and value.startswith(("=","+","-","@")) else value)
                  for key,value in row.items()}
            writer.writerow(safe)
        return Response(buffer.getvalue(),media_type="text/csv",
                        headers={"Content-Disposition":f'attachment; filename="{filename}.csv"'})

    @app.get("/api/export")
    def export(request: Request):
        filters=dict(request.query_params)
        kind=filters.pop("format","json")
        return download(runtime().store.query(limit=200000,**filters),kind,"gestureguard-audit")

    @app.get("/api/evaluation/export")
    def evaluation_export(request: Request):
        filters=dict(request.query_params)
        kind=filters.pop("format","json")
        data=summarize(runtime().store.query(limit=200000),**filters)
        return download(data["metrics"] if kind=="csv" else data,kind,"gestureguard-evaluation")

    @app.get("/api/replay/export")
    def replay_export():
        events=runtime().store.query(limit=20000,type="input_observation",session_id=runtime().session["id"])
        return download({"kind":"recorded_observations","observations":[e["details"] for e in reversed(events)]},"json","gestureguard-replay")

    @app.post("/api/replay")
    def replay(payload: dict):
        runtime().load_replay(payload)
        return {"ok":True}

    @app.get("/api/camera/frame")
    def camera_frame():
        frame=runtime().vision.jpeg() if runtime().source=="live" else None
        if frame is None:
            raise HTTPException(503,"No live camera frame. Select Live Camera or use Simulated Test Input.")
        return Response(frame,media_type="image/jpeg",headers={"Cache-Control":"no-store"})

    @app.websocket("/ws")
    async def websocket(socket: WebSocket):
        if socket.headers.get("origin") not in ALLOWED_ORIGINS|{None}:
            await socket.close(code=1008)
            return
        await socket.accept()
        try:
            while True:
                await socket.send_json(await asyncio.to_thread(runtime().snapshot))
                await asyncio.sleep(.1)
        except (WebSocketDisconnect,RuntimeError):
            pass

    distribution=ROOT/"frontend"/"dist"
    if distribution.exists():
        app.mount("/",StaticFiles(directory=distribution,html=True),name="frontend")
    else:
        @app.get("/",response_class=HTMLResponse)
        def home():
            return '<h1>GestureGuard HMI backend is running</h1><p>Build the frontend: cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</p><a href="/docs">API documentation</a>'
    return app


app=create_app()
