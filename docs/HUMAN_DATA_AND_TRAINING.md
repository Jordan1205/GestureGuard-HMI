# Human recording and classifier experiments

Research checked on 6 November 2026. No real-human recognition benchmark or custom-model training has been completed for this revision. A small official license document was downloaded for inspection; no external person's images, video or landmark dataset was downloaded. The live recognizer remains MediaPipe plus the tested geometry/temporal interaction pipeline. No custom classifier is selected automatically.

## Dataset findings and download decision

The [official HaGRID repository](https://github.com/hukenovs/hagrid) describes real-person indoor RGB images, subject IDs, variable lighting and camera distance, with original subject-disjoint splits. Its [class list](https://github.com/hukenovs/hagrid/blob/master/constants.py) offers candidate labels below. These are semantic candidates requiring image review, not an assertion that two datasets define poses identically.

| GestureGuard target | HaGRID candidate | Required check |
|---|---|---|
| Open Palm | `palm`, possibly `stop` | Review finger extension/orientation and retained split provenance |
| Closed Fist | `fist` | Verify thumb/finger pose, crop and landmark detection |
| Thumb Up | `like` | Verify upward thumb and mirrored orientations |
| Victory | `peace`, `peace_inverted` | Keep orientation variants separately before deciding equivalence |
| Pointing Up | `one` | Confirm index-up pose; do not merge generic pointing labels blindly |
| Pinch | No exact required category | `ok`, `thumb_index` and two-hand categories are not automatic substitutes |
| ILoveYou | No exact required category | `rock` and `call` are different finger configurations |
| Neutral / negative movements | `no_gesture` | Useful static negatives, but not a recording of idle temporal movement |

### HaGRID license nuance

The README calls the license a variant of Attribution-ShareAlike 4.0. The linked [specific English license PDF](https://github.com/hukenovs/hagrid/blob/master/license/en_us.pdf) was actually downloaded and all five pages were extracted/read. Its first-page footnote explicitly states that this is **not a Creative Commons license**: it is a custom reworking. Do not relabel it simply as CC-BY-SA based on a mirror's metadata.

The license text grants reproduction/adaptation rights subject to its terms, including retained attribution/notices, an indication of changes and a license link; distributed adaptations carry specified same-license-element conditions. It also distinguishes privacy/publicity/portrayal rights from the copyright grant. Preserve the exact upstream text and provenance when planning a subset, and have the supervisor check the intended use and redistribution before publishing data or a derived artifact. This project does not redistribute HaGRID material or claim the custom terms have been resolved for a proposed public dataset release.

The [official download instructions](https://github.com/hukenovs/hagrid#downloads) offer gesture archives around tens of gigabytes and a 119.4 GB reduced-image archive. That is disproportionate to this repair. A third-party [30k mirror](https://huggingface.co/datasets/cj-mills/hagrid-sample-30k-384p) is still about 1 GB and declares a generic CC license; that declaration does not resolve the upstream custom-license nuance or establish retained participant grouping. No image subset was downloaded. A future subset must retain `user_id`, original split, image IDs, exact license/attribution, label review, image hashes and source version. Auto-annotated demographic metadata must not be treated as ground-truth identities or proof of demographic fairness. No glove coverage was verified.

### Other real-human video option

[Qualcomm's official Jester page](https://www.qualcomm.com/developer/software/jester-dataset) offers genuine webcam clips with Thumb Up, Stop Sign and negative/other-motion classes. It is a potential temporal-negative supplement. The page specifies research-purpose terms and links its own Data License Agreement; it is not an unrestricted public-domain source. It is approximately 22.8 GB, does not directly supply the complete GestureGuard static vocabulary, and would require checking subject/split provenance. It was not downloaded or used. Public-data access alone does not establish label compatibility or remove a need for held-out local-camera testing.

Synthetic video generation was skipped: unverified generated hand anatomy would not address the immediate webcam usability defect or replace real held-out participants.

## Collect a small, useful local dataset

Use Gesture Studio's explicit consent-controlled recording tool. The camera must be live; simulated/replayed inputs cannot become human training records. During recording, interaction is locked so posing commands cannot start a station. Images are optional and separately opted into; landmark samples and labels alone are sufficient for this experiment. Recordings stay in ignored `data/recordings/<recording-id>/manifest.json` and `samples.jsonl`. Do not commit these files or move them into public fixtures.

Collect all seven positive gestures, neutral hands and varied non-command movements. Use pseudonymous operator IDs. Repeat on at least three independent recording occasions, recording every label on each occasion; change camera placement, lighting, background, hand orientation and left/right hand where comfortable. Record glove conditions explicitly only when actually tested. Include transitions, partial hands and ordinary hand movements rather than only stationary textbook poses. Review labels visually when consented images exist; auto-classifier output is a prediction, not the expected label.

For participant-disjoint experiments collect at least three participants/groups covering all classes. For a two-student pilot, independent session grouping is possible, but it measures session transfer within those people, not unseen-person performance. All clips from the same independent occasion must retain the same experimental `session_id`; do not create new session IDs merely to make a split pass. Neighboring frames from one recording never belong to different splits.

## Approaches and measured selection rule

| Approach | Implementation | Current status |
|---|---|---|
| A: unchanged pretrained recognition | Recorded raw canned category/score; existing geometric Pinch remains separately identifiable | Model unchanged; physical-camera benchmark pending |
| B: temporal interaction evidence | Original hard gating versus improved elapsed-time consensus/hysteresis on the same raw observations | Engineering regressions run; human improvement unmeasured |
| C: lightweight custom landmarks | Optional 64-tree CPU Random Forest, bounded depth and validation-only rejection threshold | Training/evaluation code provided; no real dataset trained |

The feature extractor uses 67 numbers: wrist-centered, palm-scaled image-plane coordinates aligned to the palm axis, mirrored to a consistent hand convention, projected joint-angle cosines and normalized fingertip gaps. It removes translation, uniform scale, in-plane rotation and reflection. It deliberately ignores uncalibrated `z`; it does not remove perspective, occlusion or out-of-plane pose variation. The actual frame aspect ratio should accompany samples. Joint-angle features are included as a testable design choice; their benefit has not been established by human ablation data.

The optional [scikit-learn Random Forest API](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html) was checked through Context7. No Model Maker/TensorFlow training stack was adopted. Training requires usable positive/negative human samples and disjoint train/validation/test groups, checks class coverage in every partition and refuses to fall back to frame splitting. Threshold selection touches validation data only. The report records seed, groups, source-data fingerprint and sklearn version. Test groups must remain untouched while choosing features/settings/models; any further tuning requires a fresh test group.

The live application never loads a pickle/joblib model or automatically adopts a custom result. The experiment exports numerical trees as bounded JSON and records them as offline-only. This avoids executable Python-object loading, a risk described in the official [model persistence guidance](https://scikit-learn.org/stable/model_persistence.html). A forest vote score still is not a calibrated probability of correct or safe intent.

Only consider live custom integration after it beats the unchanged recognizer on independently held-out real-person classes and unknown movements, and after end-to-end confirmation, release and idle-motion trials. A more complex model or a higher internal score is not evidence of improvement.

## Run optional training and paired evaluation

The default application does not require sklearn. After collecting suitable real samples:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-training.txt
.\.venv\Scripts\python.exe scripts/train_classifier.py --group-by participant_id
```

The script writes a numeric JSON forest and validation/test report under ignored `data/models/`. With genuinely independent sessions instead of three participants, explicitly acknowledge the narrower claim:

```powershell
.\.venv\Scripts\python.exe scripts/train_classifier.py --group-by session_id --allow-session-split
```

Evaluate the exact same held-out recordings for raw recognition, original threshold output and improved temporal output:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_recordings.py --group-by participant_id --held-out-groups P03 --settings data/settings.json
# Optional custom comparison on the forest's untouched test groups:
.\.venv\Scripts\python.exe scripts/evaluate_recordings.py --group-by participant_id --held-out-groups P03 --model data/models/forest-experiment.json
```

Replace `P03` with an actual untouched group from the recorded split; the script rejects known training/validation overlap. Omitting `--settings` freezes and records engineering defaults rather than loading mutable calibration silently. With no human data, evaluation emits `no_human_recordings`, zero samples and absent metrics; training refuses to create a model.

Reports include per-gesture precision/recall, confusion matrices, unknown rejection, measured inference duration when present, target-hold completion, elapsed time to a completed hold, interruption counts and condition breakdowns. `raw_mediapipe` / `raw_canned_mediapipe` describe the genuine unchanged canned category; that vocabulary has no Pinch. `improved_filtered_candidates` describes fresh supported temporal candidates from interpreted `gesture` / `score`, including geometry, before command authorization. It is not committed-action accuracy. The original hard-gate component reconstructs commit `427707e`'s pinch override and quality scale from recorded tip ratio, including its missing curled-fist extension guard. Filtering does not retrain the canned model or change its raw classification accuracy.

The hold comparison isolates the original score-gating/stability component, not the complete original FSM. Static gesture clips cannot establish successful station-command completion, command false activations per idle minute, or time to successful command. Those fields remain absent until full, independently annotated interaction trials are collected through Evaluation Lab. Test known gestures plus deliberate non-command hand motion, measure idle exposure, review executed-command intentions, and report both completion and accidental commits. Preserve failures and unknowns in the denominator.

## Reproduction and privacy record

- No public human images/landmarks were used in training for this revision.
- The only downloaded upstream file was the 157,632-byte HaGRID license PDF, stored under ignored `data/research/` for inspection.
- Engineering feature/JSON-forest/hold tests use explicitly synthetic numeric fixtures. Their outcomes are not human accuracy results.
- The evaluation CLI was executed with the currently empty local dataset and correctly produced `no_human_recordings`; there is no before/after human score to report.
- Required next work: consented real recordings, label review, group-disjoint validation/test, frozen settings, end-to-end/idle trials, and an optional custom-model experiment only if these data justify it.
