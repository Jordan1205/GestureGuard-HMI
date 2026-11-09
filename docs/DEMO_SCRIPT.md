# Five-minute FYP demonstration

Use a laptop browser at 1366×768 or above, with the application already started. Choose Presentation Mode. The source label must remain visible throughout. Use the camera only after its hand-tracking path has been checked on this laptop. If it is unavailable, say: “This demonstration uses labeled simulated input to show the command architecture; it is not live recognition.”

| Time | Presenter action | Explain |
|---|---|---|
| 0:00–0:35 | Show Control Center, three stopped stations, LOCKED state and source label | The project is an intent-aware interface to simulated stations. It does not operate physical machinery or provide an emergency stop. |
| 0:35–1:10 | Run locked accidental-gesture scenario; show rejection and unchanged station | Recognizing a command shape is insufficient evidence that the operator intends to act. |
| 1:10–2:00 | In Live Camera, hold Open Palm in Easy Demo (or the configured distinct sign) to unlock, release, hold Thumb Up; otherwise run the confirmation scenario | Follow the hold progress. A stable command becomes a preview, not an immediate commit. The target and proposed action are explicit. |
| 2:00–2:35 | Release, pinch to confirm (or explicit manual Confirm); point to running ventilation and audit event | Python authorizes and executes the command. Fan/RPM/airflow come from one deterministic simulation model. Release/cooldown prevents repeating the same held gesture. |
| 2:35–3:15 | Run ambiguous and invalid-command scenarios; then hand-loss scenario | Multiple hands, bad context, timeout, or lost tracking cancel the pending action. Sustained absence locks interaction. Explain the displayed reason. |
| 3:15–4:00 | Open Evaluation Lab and run the three-mode scripted comparison | The identical observation stream goes through fresh Baseline, Protected, and GestureGuard engines. These are actual scripted architecture outcomes, not experimental recognition accuracy. Point out empty ground-truth-dependent metrics. |
| 4:00–4:35 | Open Audit Trail, search a rejection, export JSON/CSV | Events are attributable to session, mode, source, and station. Observation logging supports replay and reproducibility. |
| 4:35–5:00 | Reset factory; show Gesture Studio settings and Demo Guide | Summarize the original interaction engine and the planned counterbalanced human study. State remaining real-camera/participant work honestly. |

## Keyboard and recovery

Use the displayed keyboard shortcuts as authoritative. Presentation mode, selection, cancel, and confirmation must be reachable without a mouse. If recognition is unreliable, cancel and switch to Simulated Test Input with its visible label; do not quietly swap sources. If a scenario is still running, stop it before manual exploration. Reset the virtual factory before the next examiner.

## Viva talking points

- MediaPipe is a pretrained dependency. Our code adds command intent, state/context, uncertainty rejection, confirmation, audit, and controlled comparison.
- Continuous duration uses monotonic time; classifier score is not a calibrated safety probability.
- Pinch is a normalized geometry heuristic; image-space calibration is not physical depth measurement.
- A frontend button does not own authorization. The same Python rules are tested independently of camera hardware.
- Protection trades speed and convenience for fewer accidental commits in the defined simulated task. Whether it helps people is a question for measured evaluation.
- Two-hand ambiguity and tracking loss choose non-commit. This is conservative interaction behavior, not certified machine safety.

For recognition troubleshooting, show Gesture Studio live preview and diagnostics before touching thresholds. Explain brief noise as paused evidence. Demonstrate the voluntary local recording panel only with explicit consent and a usable webcam; empty sample counts are honest, not a failed benchmark.
