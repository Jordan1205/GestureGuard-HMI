# Recognition diagnosis and implementation

## Verified code-level causes

At revision `427707e`, the MediaPipe result passed directly to `IntentEngine.process`. In GestureGuard, one non-neutral sample below `min_score=0.70` called `_reject`, cleared the candidate, canceled a preview and set `requires_release`. Subsequent good frames were therefore insufficient until a release occurred. A changed category also restarted the hold. This explains a self-reinforcing interaction failure even when most frames were recognizable; it does not establish recognition accuracy without intended-gesture labels.

The old geometric Pinch rule overrode every canned category whenever tip separation was small, including some curled-fist geometries. Pinch's index and classifier scores also shared a threshold despite different meanings. Unlock required a relatively unfamiliar ILoveYou sign, and the main UI emphasized scores instead of an expected action. Raw frame output, temporal rejection and command authorization were difficult to distinguish.

## Revised path

1. OpenCV capture and MediaPipe inference remain on separate workers. Each distinct fresh result is consumed once; stale results cannot accumulate supported hold time.
2. `gesture_recognition.py` preserves raw canned outputs, applies image-aspect-corrected normalized Pinch geometry, and guards against a curled index in a fist. It does not turn z into centimeters or inflate a model score.
3. `TemporalFilter` integrates supported intervals rather than frame counts. Short interruptions pause progress; long observation gaps reset it. Candidate switching has hysteresis. Strong holds require recent coherence; consistently moderate classifications require a longer supported duration and higher agreement.
4. Unknown classification, brief tracking gaps and insufficient evidence have their own diagnostic statuses. Ordinary fluctuations do not produce the old release latch. Explicit ambiguity/multiple hands still block immediately; sustained loss cancels pending intent. Automatic absence/inactivity locking remains.
5. While LOCKED, a deliberate Open Palm hold unlocks Easy Demo. The distinct activation option remains configurable. While unlocked, a short stable Open Palm cancels/releases; it cannot start a station. A single Palm classification blip during Thumb Up → Pinch does not cancel the preview.
6. Start/pause still require context permission, visible preview and separate fresh confirmation. A completed action requires a credible release and cooldown; weak unknown frames cannot silently release the repeat latch.

`min_score` remains 0.70. Default moderate/coherence/time settings are explicitly provisional engineering choices, not human-data calibrated thresholds. Per-gesture overrides stay empty until configured or explicitly applied from measured calibration. Pinch acceptance uses `ratio <= pinch_ratio` plus eligible geometry and elapsed evidence, independently of classifier thresholds.

## Diagnostics and voluntary recording

Gesture Studio shows the real preview, hand count, raw canned class/score, interpreted and filtered class, candidate, threshold kind, tracking, evidence progress, interruptions, FPS/latency, lock state and decision reason. The dashboard prioritizes the next action.

Each recording requires explicit consent and a streaming live source. A dedicated worker samples distinct inference records at up to 10 Hz into local JSONL and a manifest, with optional JPEGs only if selected. The simulation command path is locked during capture. Source/session changes stop collection. Simulated/replayed observations cannot become human training samples. All recording/model/research artifacts remain under ignored `data/`.

Calibration requires repeated correctly labeled positives and actual visible-hand neutral/negative examples before suggesting a classifier threshold. Confusing negatives or poor agreement with the intended label withhold the suggestion. Applying eligible suggestions is a separate explicit operation. Calibration-set label agreement is not held-out accuracy, and hold duration is not automatically inferred without appropriate task evidence.

## Evaluation boundaries

Automated score trajectories, geometry fixtures and mock-camera samples are synthetic engineering tests. They verify decision behaviour, not human recognition accuracy. The optional evaluator compares identical held-out real samples using canned outputs, the original score/hold component, and revised temporal evidence; frame candidates and accepted holds are named separately. Full task completion, time-to-command and false activations need annotated end-to-end interaction/idle trials and remain absent when that evidence is unavailable.

No labeled human training recordings were available. The current webcam probe still failed to open a camera. Existing live audit outputs were available for the unlabeled diagnostic inspection below. No custom human model was trained or selected; no empirical before/after improvement is claimed. See HUMAN_DATA_AND_TRAINING.md for source/license research, group-disjoint training and testing commands.

## Local launch and validation

Restart an already running backend after updating this revision. A process that imported `427707e` continues using the old engine until restarted. Default startup stays `scripts/start.ps1` on loopback port 8765. Port 8766 is an explicitly allowed loopback verification port so an existing user instance need not be terminated during QA.

On the presentation laptop: select Live Camera → show one natural Open Palm → observe raw class versus candidate and accumulation → release → Thumb Up preview → Pinch confirmation → hold the same pose and verify no repeat → deliberate neutral/cancel → ambiguity/loss checks. Record separate consented positive and negative clips across at least three independent sessions or participants before training or claiming generalization.


## Existing live-log diagnostic evidence

The already-running original local instance was read without stopping it. In the most recent 3,000 observations recorded as live for its active session, 844 contained a single hand. Within the mapped canned categories, the following predicted-category score summaries were observed:

| Predicted category | Observations | Median score | 10th percentile | Below 0.70 |
|---|---:|---:|---:|---:|
| Open Palm | 184 | 0.707 | 0.670 | 40.8% |
| Thumb Up | 384 | 0.672 | 0.606 | 68.8% |
| Closed Fist | 32 | 0.842 | 0.569 | 40.6% |

These are **unlabeled historical diagnostic outputs**, not confirmed intended gestures, balanced independent trials or calibrated probabilities. Geometric Pinch, unknown/unmapped categories and absent hands were excluded from this classifier table. Correlated frames are not independent participants. The single ILoveYou prediction is insufficient to characterize that gesture. The figures explain why hard rejection at 0.70 can create interaction friction; they do not prove recognition precision/recall or justify per-gesture empirical thresholds. The raw log, session identifiers, images and landmarks are not published. The current decision pipeline still needs independent labeled webcam validation.
