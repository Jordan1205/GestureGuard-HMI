# Evaluation protocol

## What is already measurable

Audit events expose command outcomes, rejections, tracking-loss transitions, measured inference time, throughput samples, and end-to-end command latency when recorded. These are application measurements, not proof of safe operation. Inference-output replay tests the interaction architecture; it does not measure image recognition accuracy. The deterministic comparison endpoint reports scripted counts and configuration/fixture hashes, clearly separated from human trials.

The evaluation screen leaves unsupported metrics empty. Recognition accuracy requires expected labels. Task completion requires timed, annotated tasks. False activations per idle minute requires annotated idle exposure and reviewed command labels. Zero data must never be reported as 100% accuracy or zero-error evidence.

## Research questions

1. How do Baseline, Protected, and GestureGuard differ in unintended simulated command activations during normal tasks and incidental movement?
2. What completion-time and rejection-rate tradeoffs are introduced by stability, unlocking, and confirmation?
3. How do specified lighting, distance, and glove conditions affect recognition and interaction outcomes on the tested camera?

## Small feasible study

Use the same laptop, camera, view angle, background, software revision, model file, and saved settings. Start with a pilot involving the two students to improve instructions; report pilot data separately. Then recruit consenting adult volunteers, for example 6–10 participants if allowed by your supervisor. This is a proposed sample, not completed research or a statistical power claim. Use IDs P01, P02, etc.; do not use names in event exports.

Counterbalance the three mode orders across participants (ABC, ACB, BAC, BCA, CAB, CBA). Provide equal practice before each mode. Keep gesture targets, station starting state, task sequence, and incidental-movement instruction identical. Reset the factory and create a new session before each block. Record actual run duration and all exclusions. Never remove a failure just because it makes the result look worse.

Suggested primary block per participant and mode:

1. Neutral/idle exposure: 60 seconds of ordinary non-command activity in view; define permissible incidental movements beforehand. An observer reviews every activation. Annotate exposure time and whether each activation was intended and occurred during idle.
2. Five trials each of Thumb Up, Closed Fist, Victory, Pointing Up, Open Palm, Pinch, and unlock (35 labeled trials). Use a spoken or on-screen expected-gesture cue and independent observer labeling. Score a trial by a predeclared rule, e.g. the highest-quality stable recognized result within a fixed 3-second recognition window. Report None/reject as a recognition error, separately from a correct protective rejection in a command task.
3. A short station task: unlock where needed, start ventilation, pause ventilation, select conveyor, start/pause it, select inspection, start/pause it. Record success against this intended sequence, task onset/end, and all additional/unintended commands.
4. Protection challenges: incidental gesture while locked; two hands; changed selected station during preview; timeout; hand loss while pending; pause an already stopped station. These are architecture checks with expected outcomes, not recognition-accuracy trials.

For a bounded Diploma MVP, make normal lighting and a fixed comfortable distance the main experiment. Explore dim lighting, nearer/farther operation, and a specified glove in a smaller secondary block. Record actual lux or centimeters only if measured using an appropriate instrument; otherwise use categorical labels and image-space scale. Document glove material/color and camera resolution. Do not infer glove support from untested conditions.

## Ground-truth annotations

Append annotations to the same session metadata as the trial. Do not edit the original observation/event record. If correcting a command label, the latest valid label for that executed event is used; record the reason externally in the research log.

| Event type | Details | Interpretation |
|---|---|---|
| `recognition_label` | `expected`, `predicted`, optional trial ID | One predeclared recognition trial, not each video frame |
| `command_label` | `event_id`, `intended` boolean, `idle` boolean | Observer judgment linked to an actual executed command |
| `idle_exposure` | `duration_seconds`, optional block ID | Measured idle observation time |
| `task_result` | `success` boolean, `duration_seconds`, optional task ID | Observed outcome and elapsed task time |
| `performance_sample` | `fps`, `recognition_ms`, `source` | Measured live engine performance |

Use the application's annotation endpoint if provided, or its documented session workflow. A command label referencing a missing/filtered executed event is excluded. Apply filters consistently to command events, their labels, and exposure records. Do not mix scripted and live input when reporting real-camera results.

## Metric definitions

| Metric | Definition and denominator |
|---|---|
| Recognition accuracy | Correct expected/predicted labeled trials / all valid labeled trials × 100%; include confusion matrix in the report |
| Unintended activations | Executed commands independently labeled unintended; report reviewed command sample count |
| False activations per idle minute | Idle commands labeled unintended / annotated idle seconds × 60; label all commands in the exposure |
| Completion rate | Successful annotated tasks / all annotated tasks × 100% |
| Task time | Seconds from task cue to predeclared end; report successes/failures and median/IQR as well as mean |
| Rejection rate | Rejected events / (rejected + executed events) × 100%; event-based, not per-frame |
| Tracking loss | Transitions from hand presence to lost tracking |
| Recognition latency | Measured model processing milliseconds; report distribution/hardware |
| End-to-end latency | Candidate onset to commit, including deliberate hold/confirmation; do not compare it directly to inference time |
| FPS | Measured inference throughput, not configured camera frame rate |

The current aggregate false-activation rate requires at least one reviewed idle command label. For a reviewed exposure with no commands, report zero with the exposure duration in the experimental worksheet and clearly distinguish that reviewed result from unannotated empty data.

## Reproducibility package

Archive Git revision, Python/npm lockfiles, settings JSON, model checksum, anonymized event exports, trial/annotation sheet, hardware/OS/camera details, participant mode order, fixture hash, comparison configuration hash, inclusion criteria, and analysis script. Use the CSV/JSON export to recompute figures rather than transcribing UI numbers. Keep raw data and derived results separate. Preserve failures and explain any missing records.

For two students and a small convenience sample, descriptive statistics and paired participant plots may be sufficient. Do not claim statistical significance without a suitable prespecified analysis. Report threats to validity: learning/order effects, observer bias, small sample, one camera, simulated machinery, uncontrolled light, category-score calibration, and the extra confirmation burden. Include a supervisor-reviewed ethics/consent procedure before recruitment.

## Completion checklist for the report

- Real webcam acceptance test on the demonstration laptop.
- Pilot calibration and condition definitions frozen before main data collection.
- Labeled recognition trials and reviewed idle exposure collected.
- Counterbalanced human task sessions complete with sample counts.
- All modes compared with both deterministic architecture tests and separate human measurements.
- Figures recomputed from exports, limitations stated, and no scripted result presented as real recognition performance.
