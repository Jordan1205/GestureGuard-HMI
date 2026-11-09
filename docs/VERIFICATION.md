# Recognition usability verification — 7 November 2026

This section supersedes the original implementation results retained below.

- **137 backend tests passed**, one existing upstream Starlette/AnyIO deprecation warning. New coverage includes moderate-score consensus, score/category/Palm fluctuations, brief and sustained tracking loss, fresh final evidence, repeated-action suppression, both activation profiles, independent Pinch geometry, exact new-engine observation replay, consented recording/privacy, calibration negatives, group-disjoint offline learning and numeric model validation.
- Strict TypeScript and the Vite production build passed. Latest reviewed build: `index-CKKwhL4r.js` / `index-CGYrHNxn.css`. No runtime dependency was added; Scikit-learn remains an uninstalled optional training extra.
- `pip check` found no broken requirements. The offline evaluation CLI actually returned `no_human_recordings`, 0 labeled samples. No human custom model was trained or enabled.
- Actual browser checks exercised Easy Demo Open Palm → release → command preview → separate Pinch → simulated station start, the new Studio diagnostics, unchecked recording/image/application consent, blocked recording without a live camera, honest empty calibration, camera recovery and responsive layout. Source-specific raw-score labels and pinch distance units were inspected. Mobile width remained within390px.
- The webcam was probed again through the real OpenCV/MediaPipe service and could not open. This does not demonstrate live recognition improvement on the user's camera. The older user instance at8765 was left running; QA used a separate loopback instance at8766.
- Historical live audit observations were inspected without publishing raw logs or identifiers: 384 predicted Thumb Up observations had median score0.672 and68.8% below0.70. These unlabeled correlated outputs support the old hard-gate diagnosis, not accuracy, intended-command success or a calibrated threshold claim. See RECOGNITION_USABILITY.md.
- Focused screenshot review accepted all three listed fixes: functional type size, source-honest raw values and camera-unavailable recovery instructions. The inherited Geist/canvas-grid detector advisories were retained to preserve the established interface.
- New screenshots: `recognition-control-center-1366.png`, `recognition-studio-1366.png`, `recognition-unavailable-1366.png`, `recognition-studio-mobile-390.png`. They show actual application outputs; injected observations remain explicitly labeled. Original screenshots below remain historical artifacts.

Remaining: restart the original backend to load this code; collect consented labeled clips/negative movements across independent sessions or people, validate provisional filter settings on the actual webcam, run held-out paired classification/interaction evaluation, then consider whether the optional custom classifier improves measured performance. No real-world success-rate or before/after accuracy claim is made.

---

# Verification record — 6 November 2026

## Automated checks actually run

- Python 3.11.9 isolated virtual environment: **84 tests passed**, one upstream Starlette/AnyIO deprecation warning. Latest full run: `python -m pytest backend/tests -q`, 3.91 seconds.
- Coverage includes FSM transitions, continuous holds, repeated gestures, confirmation timeout, tracking loss, uncertainty, context changes, source switching, deterministic simulations, SQLite serialization, exact logged replay, three-mode differences, API/WebSocket boundaries, replay validation, annotations, and normalized pinch geometry.
- Regressions cover preserving the selected mode in Scenario Runner, sampling monotonic time after the command lock, and preventing full-history aggregation inside operational snapshots.
- Strict TypeScript check and Vite 7.3.7 production build: **passed**. Final assets: `index-DildylrQ.js`, `index-BQxFxomW.css`.
- `pip check`: no broken requirements. Frontend dependency installation reported zero npm audit vulnerabilities at installation; this is a dated dependency check, not a security certification.
- MediaPipe 0.10.21 / OpenCV 4.11.0 / NumPy 1.26.4 imported successfully. The official version-1 model initialized and performed actual inference on a blank 640×480 fixture, correctly returning no hand landmarks. Its downloaded checksum is pinned in the downloader and model manifest.

## Browser checks actually performed

Playwright exercised the running local application, including all five screens, manual preview/explicit confirmation, Simulated Stop, a complete timed simulated unlock/start/pinch sequence, pending cancellation, audit search, reproducible comparison rendering, unavailable-camera recovery, presentation controls, Enter confirmation, Escape cancellation and keyboard station selection.

The real-time simulated sequence committed a start and changed ventilation to running with model-derived RPM/airflow. This verifies the interaction/simulation path; it does not measure webcam gesture recognition.

The equivalent-stream comparison processes 292 identical scripted observations through independent fresh engines and includes fixture/configuration hashes. Its outcomes and intention labels are explicitly scripted. They are not participant results, recognition-accuracy estimates or safety guarantees.

## Interface audit

Applied the installed `gpt-taste` guidance and Impeccable craft checks within the user's operational industrial brief. The landing-page-specific rules were intentionally superseded by this application's operational requirements.

A separate screenshot reviewer inspected the original and corrected captures. All listed fixes were accepted: larger operational labels, projector fit, unavailable telemetry dashes, mobile source reflow, source selection semantics, accessible collapsed navigation, accurate gesture count, mode-preserving demo instructions and natural-height evaluation charts. Captures were corrected to start at the document top and wait for the intended state.

- At **1920×1080**, both pending and LOCKED presentation captures have document height 1080 with essential controls visible. Source labels compute to 12px; primary presentation actions/status use larger type.
- At **1366×768**, the complete operational screen scrolls vertically. Vision, intent and navigation remain clear; lower station controls and timeline are accessible by scrolling. Presentation Mode provides the consolidated projector surface.
- At **390×844**, all three source options are accessible and the settled final capture has no horizontal overflow. Collapsed navigation has accessible names.
- The mechanical scanner's progress-width transition warning was fixed. Geist and the vision-canvas grid were retained deliberately: the selected taste guidance names Geist, and the grid is confined to the vision workspace. No claim of general WCAG certification is made.

## Actual screenshots

`screenshots/` contains real browser captures, not mockups:

- `control-center-1366.png` — accepted timed simulated command and running ventilation.
- `pending-1366.png` — explicit action preview awaiting confirmation.
- `gesture-studio-1366.png`, `evaluation-lab-1366.png`, `audit-trail-1366.png`, `demo-guide-1366.png` — the additional screens.
- `vision-unavailable-1366.png` — actual unavailable-camera state with absent FPS/latency.
- `presentation-1920.png`, `presentation-locked-1920.png` — pending and locked projector states.
- `mobile-390.png` — settled simulated-input mobile layout.

Screen values are real application simulation/event outputs from engineering smoke tests. They are not a participant experiment. Some mode/source controls are asynchronous; captures wait for the intended authoritative state.

## Remaining verification and limitations

OpenCV attempted to open the default webcam and returned **Camera index out of range / Cannot open webcam** in this environment. Real hand tracking, all physical gestures, lighting/glove robustness, camera FPS, recognition latency and perceptual projector legibility therefore remain unverified. Test those on the presentation laptop using the procedure in the README and evaluation protocol.

Recognition accuracy, idle false activations and human task completion require labeled participant trials; no such study has been completed. Full evaluation/export queries are bounded to 200,000 recent events; keep sessions short and export them individually. Wall-clock replay uses a 20 Hz coordinator and can skip very short intervals; exact offline comparison/replay tests are the deterministic evaluation route.

The optional OpenSCAD webcam support is unprinted and not load-tested. ESP32 indicators, physical machinery integration and certified safety control are outside the delivered prototype. No physical machine control is implemented.
