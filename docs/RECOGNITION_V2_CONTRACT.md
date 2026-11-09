# Recognition usability update contract

Root owns vision.py/runtime.py/api.py/recording.py and integration. Engine agent owns domain.py/intent_engine.py/gesture_recognition.py/temporal_filter.py. Frontend agent owns frontend. Human-data agent owns learning.py, offline training/evaluation scripts and dataset research. Do not edit another owner's files concurrently.

## Settings and diagnostics

Settings now contain numbers, strings, booleans and a per-gesture threshold dictionary. Existing settings JSON loads by merging defaults. `easy_demo=true`, `activation_gesture='Open_Palm'` by default; the distinct `ILoveYou` option remains available. No invented empirically calibrated defaults.

`snapshot.engine.diagnostics` contains `raw_gesture`, `raw_score`, `filtered_gesture`, `candidate_gesture`, `threshold`, `tracking_status`, `evidence_progress`, `hold_interruptions`, `status`, `unlocked`, `activation_gesture`, and optional `acceptance_path`. `snapshot.engine.unlocked` is authoritative. Existing engine keys remain. Raw scores are unchanged, uncalibrated scores. Vision supplies a new immutable inference timestamp only when a new inference result exists; never accrue time by recycling old observations.

## Opt-in local recording API

- GET `/api/recording`: `{active, recording_id:null|string, label:null|string, elapsed_seconds, duration_seconds, progress:0..1, samples, usable_samples, completed_recordings, dataset_samples, camera_ready, message, save_images:false|true}`. Also provided as `snapshot.recording` without file reads.
- POST `/api/recording/start`: `{consent:true,label:'ILoveYou'|'Open_Palm'|'Closed_Fist'|'Thumb_Up'|'Victory'|'Pointing_Up'|'Pinch'|'None'|'Negative',duration_seconds:3..60,save_images:false}`. Conditions/operator come from active pseudonymous experimental session. Requires Live Camera streaming. Consent required for each clip. Recording locks command interaction until stopped/completed, so performing training gestures cannot actuate stations.
- POST `/api/recording/stop`: `{}`. Saves actual collected frames/landmarks locally. No synthetic or replay input accepted. Source switch/close also stop recording.
- GET `/api/calibration`: `{report_id, recordings, samples, by_gesture:[{gesture,samples,correct_samples,agreement,raw_score_median,raw_score_p10,threshold_suggestion:null|number,note}], suggestions:{gesture_thresholds?:{},hold_seconds?:number}, can_apply:bool, warnings:string[], source:'local_real_webcam', status:string}`. Reads local clips only on explicit request, not inside live snapshot/command lock. Never manufactures sample counts.
- POST `/api/calibration/apply`: `{consent:true,report_id:string}`. Applies only eligible conservative suggestions from that report; interface locks. Empty/insufficient report rejects. Settings remain inspectable and user can revert.

Recordings are stored in ignored `data/recordings/<uuid>/manifest.json` and `samples.jsonl`, optional timestamped JPEGs only if explicitly selected. A sample: `{timestamp:relative_seconds,captured_at:monotonic,expected:label,raw_gesture,raw_score,gesture,score,hands,landmarks:[[x,y,z]*21] or [],recognition_ms,hand_scale,pinch_ratio,source:'live',origin:'real_webcam'}`. Manifest contains `participant_id` pseudonym, `session_id`, conditions, label, origin, model/config, sample counts, consent. No webcam images/landmarks go into Git. Never infer physical centimeters from z.

Frontend display live camera and diagnostics in Gesture Studio, voluntary consent checkbox unchecked by default, explicit red recording indicator and progress, negative/neutral examples, source restrictions, completed sample counts and calibration report with apply confirmation. Startup and normal UI appearance preserved.

Offline optional classifier is never selected automatically. Training requires genuine human recordings and group-disjoint train/validation/test sessions or participants. Reports include raw-vs-filtered results on same held-out records, precision/recall/confusion, unknown rejection and measured latency when present. No synthetic numeric results in human benchmark fields.
