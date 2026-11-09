# GestureGuard HMI architecture

**Academic title:** An Intent-Aware Touchless Human–Machine Interface Using Computer Vision for Simulated Industrial Workstations.

## The contribution

The project studies the decision between recognizing a gesture and committing a command. MediaPipe supplies pretrained hand/gesture inference. Our contribution is the Python interaction architecture: monotonic stability filtering, deliberate unlock, release gating, context permissions, explicit preview/confirmation, cancellation on uncertainty, source-attributed audit events, and repeatable comparison of control configurations. It is an integration and interaction-engineering contribution, not a new neural network or a certified industrial safety controller.

The question to investigate is: **Does this protected interaction architecture reduce unintended command activations in a simulated workstation task, and at what cost in completion time and rejection rate?** Do not replace this question with an unsupported claim of improved recognition accuracy.

## Boundaries

| Module | Responsibility | Must not own |
|---|---|---|
| `vision` | OpenCV capture, background inference, annotated preview, measured processing time | Station authorization |
| `gesture_recognition` | Convert landmarks/categories into observations; normalized pinch geometry | Physical distance estimation in centimeters |
| `intent_engine` | Stability, finite-state machine, unlock/preview/confirm/release/timeouts | Camera drivers or React state |
| `command_router` | Check target station and operation permissions | Model inference |
| `simulation` | Deterministic workstation state and metrics updated by elapsed time | Real machinery or OS automation |
| `event_store` | SQLite append/query and structured JSON payloads | Ground-truth judgments inferred from classifier score |
| `evaluation` | Recorded metrics, annotations, deterministic comparison | Fabricated participant results |
| `api` / runtime | Local HTTP/WebSocket integration, source orchestration, lifecycle | Blocking inference on the async event loop |
| `frontend` | Present authoritative snapshots; explicit manual commands; accessible controls | The only implementation of safety/authorization logic |

The browser sends intentions; Python decides whether they are permitted. Refreshing a tab does not invent a new simulation. Runtime queues and the latest-frame handoff keep capture/inference from blocking HTTP/WebSocket delivery. Camera work is explicitly started by choosing Live Camera. Closing the process releases camera resources through application shutdown.

## Observation and timing

Every observation has a monotonic timestamp, gesture, classifier score, hand count, ambiguity flag, source, and measured inference duration where available. Canonical source labels distinguish live camera, recorded replay, and simulated/scripted input. Timed holds use seconds rather than frame counts, so dropped frames do not silently change the configured duration.

Do not interpret MediaPipe category scores as calibrated probabilities. Landmark `z` is not a ruler. Pinch uses the thumb/index tip separation relative to a hand-scale reference. Operating-distance calibration uses image-space hand scale, so it supports a comfortable range within this camera setup rather than calibrated physical distance.

The reference scale is palm width between landmarks 5 and 17 relative to image width, with normalized-y aspect correction. Pinch metadata uses `score_kind=geometric_quality_index`; pretrained classes use `score_kind=classifier_output`. The pinch quality index is a deterministic geometry score and must not be pooled with classifier outputs as if both were calibrated probabilities.

## Gesture mapping

| Input | Meaning |
|---|---|
| ILoveYou | Configurable distinct activation alternative |
| Open Palm | Easy Demo held unlock while locked; short stable cancellation/neutral after unlock |
| Thumb Up | Request start of the selected simulated station |
| Closed Fist | Request pause |
| Victory | Select the next workstation |
| Pointing Up | Select the previous workstation |
| Pinch | Confirm a pending action |
| No hand / None | Hand absence or neutral release, depending on tracking |

## State machine

The implemented transition table in `intent_engine.py` is authoritative and unit-tested. These are the operational roles:

| State | Meaning | Typical exit |
|---|---|---|
| LOCKED | Command gestures cannot activate a protected station | Held configured activation → READY |
| READY | Awaiting a new deliberate gesture | Command candidate → GESTURE_CANDIDATE |
| GESTURE_CANDIDATE | Measuring a continuous hold | Stable and permitted → ACTION_PREVIEW |
| ACTION_PREVIEW | Proposed command and fixed target are visible | AWAITING_CONFIRMATION |
| AWAITING_CONFIRMATION | A separate pinch or explicit manual confirmation is required | Accepted → EXECUTING; timeout/loss/change → cancellation |
| EXECUTING | Python router applies the authorized simulated action | COOLDOWN |
| COOLDOWN | Repetition is blocked | Elapsed cooldown and neutral release → READY |
| REJECTED | An actionable reason explains why no commit occurred | Release/recovery or locking |

The UI may not visibly dwell in a transient state such as EXECUTING because the model update is fast; the audit preserves transitions. Context validation happens before preview and before commit. A selected-station change must invalidate an old pending action, never silently retarget it. Brief tracking fluctuations pause evidence without committing. Sustained loss cancels pending intent; longer absence returns the system to LOCKED. Manual controls are a labeled accessibility/testing path, and remain subject to backend rules for start/pause in GestureGuard mode. Simulated Stop is a direct, logged simulation-only control.

## Comparable modes

| Feature | Baseline | Protected | GestureGuard |
|---|---|---|---|
| Isolated deterministic workstation simulation | Yes | Yes | Yes |
| Minimal gesture mapping | Yes | Yes | Yes |
| Deliberate unlock, continuous hold, cooldown/release | No | Yes | Yes |
| Explicit command preview and separate confirmation | No | No | Yes |
| Context/uncertainty explanations in interaction architecture | Minimal | Limited | Yes |
| Structured event collection for comparison | Yes | Yes | Yes |

The factory still refuses impossible state operations in every mode; Baseline is intentionally permissive input mapping, not permission to corrupt the model. A/B/C evaluation uses fresh identical factory states and the same observation stream. It must also account for the deliberate extra confirmation cost in GestureGuard.

## Events, persistence, and privacy

SQLite records event type, UTC display timestamp, monotonic timing, mode, session, gesture, station, severity, message, and structured details. Monotonic clocks measure durations; UTC timestamps support readable audit history. Session metadata uses pseudonymous operator IDs and explicit lighting/distance/glove labels. Input observations support architecture replay; a replay of inference outputs does not rerun or validate the vision model.

By default the backend binds `127.0.0.1`. Camera previews and controls are local. No cloud inference, account, API credential, physical machine, PLC, or OS action is required. Do not publish the audit database or camera recordings with personal identifiers. Raw-video recording is not required for the MVP; obtain participant consent and store any separately collected recordings securely.

## Two-student ownership

Student A owns vision/recognition, calibration, fixture capture, and performance measurement. Student B owns intent engine/API, simulation, UI, and audit integration. Both review the state-machine tests and jointly run counterbalanced participant sessions. Keep changes small enough for the other student to explain in a viva. Read `EVALUATION_PROTOCOL.md` for the experiment and `DEMO_SCRIPT.md` for the presentation.


## Recognition usability revision

`temporal_filter.py` is causal and time-based: it retains a candidate through brief instability, counts only supported observed intervals, applies category-switch hysteresis and recent agreement, and requires a fresh matching final observation. The strong path uses the configured per-gesture/default threshold; a moderate path requires an extended supported hold and greater recent agreement. Sustained ambiguity or missing evidence cannot coast into a command. GestureGuard uses the revised filter; Baseline stays raw and Protected retains its simpler legacy hold/release behavior for comparison.

Pinch is a geometry modality with its own distance limit; canned score, interpreted geometry index and temporal evidence have separate diagnostic fields. Curled-fist geometry is guarded. `recording.py` runs consented collection on a separate worker, locks command interaction while active, and only saves real live samples locally. Normal performance audit events no longer persist hand landmark arrays. `learning.py` supplies optional offline grouped experiments; no custom model replaces MediaPipe without real independent validation. See RECOGNITION_USABILITY.md and HUMAN_DATA_AND_TRAINING.md for the exact protocol and limitations.
