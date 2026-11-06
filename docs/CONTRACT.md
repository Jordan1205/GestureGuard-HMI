# Integration contract

Python package `backend/gestureguard`. Core modules owned by engine agent: `domain.py`, `intent_engine.py`, `simulation.py`, `command_router.py`, `event_store.py`, core tests. Root owns vision, runtime, evaluation, API and scripts. Frontend agent owns frontend only.

Core public API (all timestamps monotonic seconds):
- `Observation(timestamp: float, gesture: str='None', score: float=0, hands: int=0, ambiguous: bool=False, source: str='simulated', recognition_ms: float=0, **optional)` dataclass; canonical gestures `ILoveYou` (unlock), `Open_Palm`, `Closed_Fist`, `Thumb_Up`, `Victory`, `Pointing_Up`, `Pinch`, `None`.
- `Settings` dataclass: `hold_seconds=.65`, `unlock_seconds=1.2`, `confirm_seconds=.5`, `confirmation_timeout=6.0`, `cooldown_seconds=.8`, `absence_lock_seconds=3.0`, `inactivity_lock_seconds=30.0`, `min_score=.7`, `pinch_ratio=.28`.
- `Factory()`: `stations` list, `selected` index; `select(index)`, `command(action, station_id=None)` returns `(bool, str)`; `tick(dt)`; `reset()`; `snapshot()` list of JSON dicts.
- `EventStore(path=':memory:')`: `append(event: dict)->dict` (id, ISO UTC timestamp), `query(limit=200, **filters)->list[dict]`, `close()`; serialize details as JSON, thread-safe.
- `IntentEngine(factory, store, settings=None, mode='gestureguard', session_id='...')`: `process(observation)`, `tick(timestamp)`, `set_mode(mode)`, `lock(reason='...')`, `manual(action, station_id=None)` (explicit manual confirmation/start/pause/stop/select/reset routes), `snapshot()->dict`, `events` recent store events; mode values `baseline`, `protected`, `gestureguard`.
- `engine.snapshot()` keys: `state`, `mode`, `gesture`, `score`, `hold_progress` (0..1), `confirm_progress` (0..1), `pending` null or {action,station_id,station_name}, `reason`, `selected_station` index, `requires_release`, `settings` dict.
- Station snapshot: `id` string `ventilation`/`conveyor`/`inspection`, `name`, `state` lowercase stopped/running/paused, `target_speed` (percent), `rpm`, `airflow`, `throughput`, `items`, `passed`, `failed`, `progress` float 0..1.
- Event keys: `id`, `timestamp` UTC ISO, `monotonic`, `type` (`gesture_recognized`, `action_proposed`, `confirmation_accepted`, `command_executed`, `rejected`, `auto_lock`, `tracking_lost`, `state_changed`, `input_observation`, `session_started` etc), `severity`, `message`, `mode`, `session_id`, `station_id`, `gesture`, `details` dict; input observation logged for replay; executed details include action, source and latency_ms.

Browser API base relative same origin (Vite proxies `/api` and `/ws` to 127.0.0.1:8765):
- GET `/api/snapshot` and WS `/ws`: bounded operational snapshot at ~10Hz: `{engine, stations, events, vision:{status,source,fps,recognition_ms,frame_age_ms,hands,landmarks, error}, session:{id,operator_id,lighting,distance,glove}, scenario:{running,name,step,total}}`. Historical aggregation is requested separately through `/api/evaluation`; it never runs inside the command lock during WebSocket snapshots.
- POST `/api/control` JSON `{action, station_id?, value?}` action `start`,`pause`,`stop`,`select`,`confirm`,`cancel`,`lock`,`reset`,`speed`. Manual start/pause creates preview in GestureGuard; confirm explicitly commits. Manual stop directly stops simulation and logs manual source. Select `station_id` or numeric `value`.
- POST `/api/input` `{gesture,score:.99,hands:1,duration:1.0,ambiguous:false}` hold simulated gesture for duration; source must be simulated, reject in live/replay.
- POST `/api/source` `{source:'live'|'simulated'|'replay'}` resets/locks pending intent. Replay plays persisted JSON observation fixture; label honestly.
- POST `/api/mode` `{mode:'baseline'|'protected'|'gestureguard'}`.
- POST `/api/settings` partial settings above plus min_hand_scale/max_hand_scale; save validated settings.
- POST `/api/scenario` `{name:'accepted'|'locked'|'ambiguous'|'confirmation'|'invalid'|'success'|'hand_loss'|'tour'}`; stop via `{name:'stop'}`.
- POST `/api/session` `{operator_id,lighting,distance,glove}` starts new session.
- GET `/api/events?search=&mode=&session_id=&operator_id=&lighting=&distance=&glove=&gesture=`.
- GET `/api/export?format=csv|json` audit export; `/api/evaluation` same filters real recorded metrics; POST `/api/evaluation/compare` deterministic scripted stream all 3 modes, results marked scripted (not recognition accuracy); GET `/api/evaluation/export?format=csv|json`.
- GET `/api/camera/frame` latest annotated JPEG; frontend img refresh ~8Hz only source live. GET `/api/health`.

No fabricated initial telemetry. Factory begins stopped; input simulated and engine LOCKED; vision not opened until live selected. Errors `{detail: human string}`. All source labels visible. No credentials/cloud.
