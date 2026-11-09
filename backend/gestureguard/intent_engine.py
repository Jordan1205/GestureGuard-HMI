"""Hardware-independent intention state machine.

Only this backend component commits gesture commands. The UI and camera merely
provide observations. Baseline deliberately omits guards for isolated comparison.
"""

from dataclasses import asdict, replace
import math
from threading import RLock
from typing import Any

from .command_router import CommandRouter
from .domain import GESTURE_ACTIONS, MODES, Observation, Settings, State
from .event_store import EventStore
from .simulation import Factory
from .temporal_filter import FilteredEvidence, TemporalFilter


VALID_TRANSITIONS: dict[State, frozenset[State]] = {
    State.LOCKED: frozenset({State.GESTURE_CANDIDATE, State.ACTION_PREVIEW, State.EXECUTING}),
    State.READY: frozenset({State.GESTURE_CANDIDATE, State.ACTION_PREVIEW, State.EXECUTING, State.REJECTED, State.LOCKED}),
    State.GESTURE_CANDIDATE: frozenset({State.READY, State.ACTION_PREVIEW, State.EXECUTING, State.REJECTED, State.LOCKED, State.AWAITING_CONFIRMATION}),
    State.ACTION_PREVIEW: frozenset({State.AWAITING_CONFIRMATION, State.REJECTED, State.LOCKED}),
    State.AWAITING_CONFIRMATION: frozenset({State.EXECUTING, State.REJECTED, State.READY, State.LOCKED, State.GESTURE_CANDIDATE}),
    State.EXECUTING: frozenset({State.COOLDOWN, State.READY, State.REJECTED, State.LOCKED}),
    State.COOLDOWN: frozenset({State.READY, State.REJECTED, State.LOCKED, State.ACTION_PREVIEW, State.EXECUTING}),
    State.REJECTED: frozenset({State.READY, State.LOCKED, State.GESTURE_CANDIDATE, State.ACTION_PREVIEW, State.EXECUTING}),
}


class IntentEngine:
    def __init__(self, factory: Factory, store: EventStore, settings: Settings | None = None, mode: str = "gestureguard", session_id: str = "local") -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown control mode: {mode}")
        self.factory, self.store = factory, store
        self.router = CommandRouter(factory)
        self.settings = settings or Settings()
        self.mode, self.session_id = mode, session_id
        self._lock = RLock()
        self.state = State.LOCKED
        self.unlocked = False
        self.now = 0.0
        self.gesture = "None"
        self.score = 0.0
        self.reason = "Hold Open Palm to unlock in Easy Demo, or use the configured activation gesture."
        self.hold_progress = 0.0
        self.confirm_progress = 0.0
        self.requires_release = False
        self.pending: dict[str, Any] | None = None
        self._candidate: str | None = None
        self._candidate_since: float | None = None
        self._confirm_since: float | None = None
        self._absence_since: float | None = None
        self._last_activity: float | None = None
        self._last_hands = 0
        self._last_gesture = "None"
        self._last_rejection: tuple[str, str] | None = None
        self._cooldown_until = 0.0
        self._current_source = "simulated"
        self._temporal = TemporalFilter()
        self._diagnostics: dict[str, Any] = {}
        self._release_since: float | None = None
        self._release_last: float | None = None

    @property
    def events(self) -> list[dict]:
        return self.store.query(limit=60)

    def _emit(self, event_type: str, message: str, severity: str = "info", **details: Any) -> dict:
        return self.store.append({"type": event_type, "message": message, "severity": severity,
            "monotonic": self.now, "mode": self.mode, "session_id": self.session_id,
            "station_id": self.factory.stations[self.factory.selected].id,
            "gesture": self.gesture, "details": {"source": self._current_source, **details}})

    def _transition(self, target: State) -> None:
        if self.state == target:
            return
        if target not in VALID_TRANSITIONS[self.state]:
            raise ValueError(f"Invalid state transition: {self.state} -> {target}")
        old = self.state
        self.state = target
        self._emit("state_changed", f"{old} → {target}", previous=str(old), state=str(target))

    def _reset_candidate(self) -> None:
        self._candidate = None
        self._candidate_since = None
        self.hold_progress = 0.0
        self._temporal.reset()

    def _reject(self, reason: str, *, locked: bool = False, require_release: bool = True) -> None:
        key = (self.gesture, reason)
        if key != self._last_rejection:
            self._emit("rejected", reason, "warning", pending=self.pending)
            self._last_rejection = key
        self.reason = reason
        self.pending = None
        self._confirm_since = None
        self.confirm_progress = 0.0
        self._reset_candidate()
        self.requires_release = require_release
        self._transition(State.LOCKED if locked or not self.unlocked else State.REJECTED)

    def lock(self, reason: str = "Interface locked by operator.") -> None:
        with self._lock:
            self.pending = None
            self.unlocked = False
            self.requires_release = False
            self._reset_candidate()
            self._confirm_since = None
            self.confirm_progress = 0.0
            self._last_rejection = None
            self._release_since = self._release_last = None
            self.reason = reason
            self._transition(State.LOCKED)
            self._emit("auto_lock" if "absence" in reason.lower() or "inactivity" in reason.lower() else "locked", reason)

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown control mode: {mode}")
        with self._lock:
            self.mode = mode
            self.lock(f"Mode changed to {mode}; pending intent cleared.")
            self._emit("mode_changed", f"Control configuration: {mode}.", configuration=self.settings.to_dict())

    def tick(self, timestamp: float) -> None:
        if not math.isfinite(timestamp) or timestamp < self.now:
            raise ValueError("Observations must use nondecreasing finite monotonic timestamps.")
        with self._lock:
            self.now = timestamp
            if self.pending:
                if self.pending["station_id"] != self.factory.stations[self.factory.selected].id:
                    self._reject("Selected station changed before confirmation; action canceled.")
                elif timestamp - self.pending["proposed_at"] >= self.settings.confirmation_timeout:
                    self._reject("Confirmation timeout; no command was executed.")
            if self.mode != "baseline" and self.unlocked:
                if self._absence_since is not None and timestamp - self._absence_since >= self.settings.absence_lock_seconds:
                    self.lock("Sustained hand absence; interface automatically locked.")
                elif self._last_activity is not None and timestamp - self._last_activity >= self.settings.inactivity_lock_seconds:
                    self.lock("Inactivity timeout; interface automatically locked.")
            if self.state == State.COOLDOWN and timestamp >= self._cooldown_until and not self.requires_release:
                self._transition(State.READY if self.unlocked or self.mode == "baseline" else State.LOCKED)
                self.reason = "Ready for a new gesture."

    def _stable(self, gesture: str, duration: float, *, change_state: bool = True) -> bool:
        if self._candidate != gesture:
            self._candidate = gesture
            self._candidate_since = self.now
            self._last_activity = self.now
        if change_state:
            self._transition(State.GESTURE_CANDIDATE)
        elapsed = self.now - (self._candidate_since if self._candidate_since is not None else self.now)
        self.hold_progress = min(1.0, max(0.0, elapsed / duration))
        return elapsed + 1e-9 >= duration

    def _preview(self, action: str, station_id: str, source: str, started_at: float | None = None) -> tuple[bool, str]:
        allowed, explanation = self.router.authorize(action, station_id)
        if not allowed:
            self._reject(explanation)
            return False, explanation
        station = self.factory.station(station_id)
        self.pending = {"action": action, "station_id": station_id, "station_name": station.name,
            "proposed_at": self.now, "started_at": self.now if started_at is None else started_at,
            "source": source}
        self._transition(State.ACTION_PREVIEW)
        self._emit("action_proposed", f"Preview: {action} {station.name}. Pinch to confirm.", action=action)
        self._transition(State.AWAITING_CONFIRMATION)
        self.reason = f"Confirm {action} of {station.name} with a separate pinch, or open palm to cancel."
        self._confirm_since = None
        self.confirm_progress = 0.0
        self._reset_candidate()
        return True, self.reason

    def _execute(self, action: str, station_id: str, source: str, started_at: float) -> tuple[bool, str]:
        self._transition(State.EXECUTING)
        allowed, message = self.router.execute(action, station_id)
        if not allowed:
            self._reject(message)
            return False, message
        self.pending = None
        self._confirm_since = None
        self.confirm_progress = 1.0
        self.reason = message
        self._emit("command_executed", message, action=action, source=source,
            latency_ms=round(max(0.0, (self.now - started_at) * 1000), 3),
            station_id=station_id, station=self.factory.station(station_id).snapshot())
        self._last_activity = self.now
        self._reset_candidate()
        if self.mode == "baseline":
            self._transition(State.READY)
        else:
            self.requires_release = True
            self._release_since = self._release_last = None
            self._cooldown_until = self.now + self.settings.cooldown_seconds
            self._transition(State.COOLDOWN)
        return True, message

    def _select(self, index: int) -> tuple[bool, str]:
        if self.pending:
            self._reject("Selected station changed before confirmation; action canceled.", require_release=False)
        self.factory.select(index)
        station = self.factory.stations[index]
        self._emit("station_selected", f"Selected {station.name}.")
        self.pending = None
        self._reset_candidate()
        self.reason = f"{station.name} selected."
        self.requires_release = self.mode != "baseline"
        self._transition(State.READY if self.unlocked or self.mode == "baseline" else State.LOCKED)
        return True, self.reason

    def _activation_gestures(self) -> set[str]:
        return {"Open_Palm", "ILoveYou"} if self.settings.easy_demo else {self.settings.activation_gesture}

    def _release_evidence(self, observation: Observation, *, absence: bool = False) -> bool:
        now = observation.timestamp
        if self._release_last is None or now - self._release_last > self.settings.max_observation_gap_seconds:
            self._release_since = now
        self._release_last = now
        duration = max(self.settings.instability_tolerance_seconds + self.settings.release_seconds, .35) if absence else self.settings.release_seconds
        if self._release_since is not None and now - self._release_since + 1e-9 >= duration:
            self.requires_release = False
            self._release_since = self._release_last = None
            return True
        return False

    def _record_diagnostics(self, observation: Observation, evidence: FilteredEvidence, path: str = "collecting") -> None:
        geometry_pinch = observation.gesture == "Pinch" and observation.metadata.get("score_kind") == "geometric_quality_index"
        if self.pending and observation.gesture != "Pinch":
            path = self.pending.get("acceptance_path", path)
        has_canned = "raw_canned_gesture" in observation.metadata
        self._diagnostics = {"raw_gesture": observation.metadata.get("raw_canned_gesture", observation.gesture),
            "raw_score": observation.metadata.get("raw_canned_score", observation.score),
            "interpreted_gesture": observation.gesture, "interpreted_score": observation.score,
            "filtered_gesture": evidence.gesture, "candidate_gesture": evidence.candidate,
            "threshold": self.settings.pinch_ratio if geometry_pinch else self.settings.threshold_for(evidence.candidate or observation.gesture),
            "classifier_threshold": self.settings.threshold_for(evidence.candidate or observation.gesture),
            "threshold_kind": "maximum_normalized_tip_distance" if geometry_pinch else "classifier_score",
            "consensus_min_score": self.settings.consensus_min_score,
            "consensus_agreement": round(evidence.agreement, 4),
            "supported_seconds": round(evidence.supported_seconds, 4),
            "strong_seconds": round(evidence.strong_seconds, 4),
            "tracking_status": "lost" if observation.hands == 0 else "multiple_hands" if observation.hands > 1 else "tracked",
            "status": evidence.status, "hold_interruptions": self._temporal.interruptions,
            "acceptance_path": path, "score_kind": "classifier_output" if has_canned else observation.metadata.get("score_kind", "classifier_output"),
            "interpreted_score_kind": observation.metadata.get("score_kind", "classifier_output"),
            "geometry": {key: observation.metadata[key] for key in ("raw_canned_gesture", "raw_canned_score", "pinch_ratio", "pinch_eligible") if key in observation.metadata}}

    def process(self, observation: Observation) -> None:
        if self.mode != "gestureguard" or not self.settings.temporal_filter_enabled:
            self._process_legacy(observation)
            return
        with self._lock:
            self.tick(observation.timestamp)
            self._current_source = observation.source
            if not math.isfinite(observation.score) or not math.isfinite(observation.recognition_ms) or (observation.hand_scale is not None and not math.isfinite(observation.hand_scale)):
                self._reject("Non-finite recognition measurement; observation discarded.", require_release=False)
                return
            self.store.append({"type": "input_observation", "message": "Raw input observation.",
                "monotonic": self.now, "mode": self.mode, "session_id": self.session_id,
                "gesture": observation.gesture, "details": observation.to_dict()})
            self.gesture, self.score = observation.gesture, observation.score
            if self.gesture != self._last_gesture and self.gesture != "None":
                self._emit("gesture_recognized", f"Raw classification: {self.gesture.replace('_', ' ')}.", score=self.score)
            self._last_gesture = self.gesture
            if observation.hands == 0:
                if self._last_hands:
                    self._emit("tracking_lost", "Hand tracking interrupted; evidence paused.", "warning")
                if self._absence_since is None:
                    self._absence_since = self.now
            else:
                self._absence_since = None
            self._last_hands = observation.hands
            if observation.hands > 1 or observation.ambiguous:
                reason = "Multiple hands detected; use one hand to remove ambiguity." if observation.hands > 1 else "Ambiguous gesture; pending action canceled."
                self._record_diagnostics(observation, FilteredEvidence(status="explicit_ambiguity"))
                self._reject(reason, require_release=False)
                return
            if observation.hand_scale is not None and observation.hands and not self.settings.min_hand_scale <= observation.hand_scale <= self.settings.max_hand_scale:
                self._record_diagnostics(observation, FilteredEvidence(status="outside_operating_range"))
                self._reject("Hand is outside the calibrated image-space operating range.", require_release=False)
                return
            # Open Palm is harmless cancellation/release when already unlocked.
            # It becomes a held activation gesture only while locked.
            neutral = observation.hands == 1 and self.gesture == "None" and self.score >= self.settings.min_score
            cancel_palm = observation.hands == 1 and self.gesture == "Open_Palm" and self.score >= min(self.settings.support_score_floor, self.settings.threshold_for("Open_Palm")) and (self.unlocked or self.pending is not None)
            if neutral or cancel_palm:
                released = self._release_evidence(observation)
                if not released:
                    # A categorical Open Palm blip during thumb-to-pinch movement
                    # pauses evidence; a deliberate short hold performs cancel.
                    evidence = self._temporal.update(replace(observation, gesture="None", score=0), self.settings)
                    evidence.status = "neutral_release_candidate"
                    self._record_diagnostics(observation, evidence)
                    self.reason = "Hold Open Palm briefly to cancel the pending action." if self.pending else "Hold neutral briefly to release the previous gesture."
                    return
                self._record_diagnostics(observation, FilteredEvidence(gesture=self.gesture, status="neutral_release"))
                if cancel_palm and self.pending:
                    self.pending = None
                    self._confirm_since = None
                    self.confirm_progress = 0
                    self._emit("action_canceled", "Open palm canceled the pending action.")
                    self.reason = "Action canceled. Open Palm never starts a station."
                self._reset_candidate()
                self.confirm_progress = 0
                if not self.pending and self.state not in {State.LOCKED, State.COOLDOWN}:
                    self._transition(State.READY if self.unlocked else State.LOCKED)
                return
            evidence = self._temporal.update(observation, self.settings)
            self._record_diagnostics(observation, evidence)
            if evidence.interrupted:
                self._emit("hold_interrupted", "Brief recognition instability paused hold evidence.", status=evidence.status)
            if observation.hands == 0 and self.requires_release:
                self._release_evidence(observation, absence=True)
            elif observation.hands != 0:
                self._release_since = self._release_last = None
            if evidence.expired:
                self.hold_progress = self.confirm_progress = 0
                self._candidate = None
                self._candidate_since = self._confirm_since = None
                if self.pending and self.pending.get("source") != "manual":
                    self._reject("Sustained tracking loss; pending action canceled." if observation.hands == 0 else "Sustained unknown or weak recognition; pending action canceled.", require_release=False)
                elif not self.pending and self.state == State.GESTURE_CANDIDATE:
                    self._transition(State.READY if self.unlocked else State.LOCKED)
            if observation.hands == 0 or not evidence.fresh_supported:
                if not self.pending or self.pending.get("source") != "manual":
                    if evidence.expired:
                        if self.pending is None and self.state != State.REJECTED:
                            self.reason = "Tracking unavailable; present one hand to resume." if observation.hands == 0 else "Insufficient sustained gesture evidence; adjust the hand or collect calibration samples."
                    else:
                        self.reason = "Tracking briefly interrupted; hold evidence is paused." if observation.hands == 0 else "Recognition evidence is paused; adjust the hand or collect calibration samples."
                return
            if evidence.candidate != self._candidate and not self.requires_release:
                self._last_activity = self.now
            if not self.unlocked:
                if evidence.candidate not in self._activation_gestures():
                    self._reject("Interface locked; hold Open Palm in Easy Demo or the configured activation gesture.", locked=True, require_release=False)
                    return
                accepted, path, progress = self._temporal.accepted(evidence, self.settings.unlock_seconds, self.settings)
                self.hold_progress = progress
                self._candidate, self._candidate_since = evidence.candidate, evidence.started_at
                self._transition(State.GESTURE_CANDIDATE)
                self._diagnostics["acceptance_path"] = path
                self.reason = "Hold Open Palm to unlock; supported evidence is accumulating." if evidence.candidate == "Open_Palm" else "Hold the distinct activation gesture to unlock."
                if accepted:
                    self.unlocked = True
                    self.requires_release = True
                    self._release_since = self._release_last = None
                    self._last_activity = self.now
                    self._reset_candidate()
                    self._transition(State.READY)
                    self.reason = "Interface unlocked. Open Palm cancels; release before the next command."
                    self._emit("unlocked", self.reason, acceptance_path=path)
                return
            if self.requires_release:
                self.reason = "Release with Open Palm or a deliberate neutral hold before the next command."
                self._reset_candidate()
                return
            if self.now < self._cooldown_until:
                self.reason = "Cooldown in progress; wait before the next command."
                self._reset_candidate()
                return
            if self.pending:
                if evidence.candidate == "Pinch":
                    accepted, path, progress = self._temporal.accepted(evidence, self.settings.confirm_seconds, self.settings)
                    self.confirm_progress = progress
                    self._diagnostics["acceptance_path"] = path
                    self.reason = "Hold the separate pinch to confirm; imperfect frames pause evidence."
                    if accepted:
                        pending = dict(self.pending)
                        allowed, reason = self.router.authorize(pending["action"], pending["station_id"])
                        if not allowed:
                            self._reject(reason, require_release=False)
                            return
                        self._emit("confirmation_accepted", "Separate pinch confirmation accepted.", acceptance_path=path)
                        self._execute(pending["action"], pending["station_id"], pending["source"], pending["started_at"])
                    return
                if evidence.candidate not in {"Victory", "Pointing_Up"}:
                    self.confirm_progress = 0
                    self.reason = "Action pending. Pinch to confirm, or Open Palm to cancel."
                    return
            action = GESTURE_ACTIONS.get(evidence.candidate or "None")
            if action is None:
                self.reason = "Gesture has no command in this state. Use a mapped gesture or Open Palm to cancel."
                return
            accepted, path, progress = self._temporal.accepted(evidence, self.settings.hold_seconds, self.settings)
            self.hold_progress = progress
            self._candidate, self._candidate_since = evidence.candidate, evidence.started_at
            self._diagnostics["acceptance_path"] = path
            if not self.pending:
                self._transition(State.GESTURE_CANDIDATE)
            if not accepted:
                self.reason = "Hold naturally; consistent moderate scores use a longer consensus hold." if not evidence.fresh_strong else "Hold steadily; supported gesture evidence is accumulating."
                return
            self._emit("gesture_accepted", "Temporal gesture evidence accepted.", acceptance_path=path,
                supported_seconds=evidence.supported_seconds, strong_seconds=evidence.strong_seconds,
                agreement=evidence.agreement, threshold=self.settings.threshold_for(evidence.candidate or "None"))
            if action in {"next", "previous"}:
                self._select((self.factory.selected + (1 if action == "next" else -1)) % len(self.factory.stations))
            else:
                station_id = self.factory.stations[self.factory.selected].id
                self._preview(action, station_id, observation.source, evidence.started_at)
                if self.pending:
                    self.pending["acceptance_path"] = path

    def _process_legacy(self, observation: Observation) -> None:
        with self._lock:
            self.tick(observation.timestamp)
            self._current_source = observation.source
            if not math.isfinite(observation.score) or not math.isfinite(observation.recognition_ms) or (observation.hand_scale is not None and not math.isfinite(observation.hand_scale)):
                self._reject("Non-finite recognition measurement; observation discarded.")
                return
            self.store.append({"type": "input_observation", "message": "Input observation.",
                "monotonic": self.now, "mode": self.mode, "session_id": self.session_id,
                "gesture": observation.gesture, "details": observation.to_dict()})
            self.gesture = observation.gesture
            self.score = observation.score if math.isfinite(observation.score) else 0.0
            changed = self.gesture != self._last_gesture
            if changed and self.gesture != "None":
                self._emit("gesture_recognized", f"Detected {self.gesture.replace('_', ' ')}.", score=self.score)
            self._last_gesture = self.gesture
            if observation.hands == 0:
                if self._last_hands:
                    self._emit("tracking_lost", "Hand tracking lost.", "warning")
                self._last_hands = 0
                if self._absence_since is None:
                    self._absence_since = self.now
                if self.pending and self.pending.get("source") != "manual":
                    self._reject("Tracking lost; pending action canceled.", require_release=False)
                self._reset_candidate()
                self._confirm_since = None
                self.confirm_progress = 0.0
                self.requires_release = False
                if self.state in {State.GESTURE_CANDIDATE, State.REJECTED}:
                    self._transition(State.READY if self.unlocked else State.LOCKED)
                return
            self._last_hands = observation.hands
            self._absence_since = None
            if self.mode == "gestureguard":
                if observation.hands != 1:
                    self._reject("Multiple hands detected; use one hand to remove ambiguity.")
                    return
                if observation.ambiguous:
                    self._reject("Ambiguous gesture; no action committed.")
                    return
                if self.gesture != "None" and (not math.isfinite(observation.score) or self.score < self.settings.min_score):
                    self._reject("Gesture score below quality threshold; hold a clear gesture.")
                    return
                if observation.hand_scale is not None and not self.settings.min_hand_scale <= observation.hand_scale <= self.settings.max_hand_scale:
                    self._reject("Hand is outside the calibrated image-space operating range.")
                    return
            if self.gesture in {"None", "Open_Palm"} and not (self.mode != "baseline" and not self.unlocked and self.gesture in self._activation_gestures()):
                self.requires_release = False
                self._last_rejection = None
                self._reset_candidate()
                self._confirm_since = None
                self.confirm_progress = 0.0
                if self.gesture == "Open_Palm" and self.pending:
                    self.pending = None
                    self._emit("action_canceled", "Open palm canceled the pending action.")
                    self.reason = "Action canceled. Ready for a new gesture."
                if not self.pending and self.state not in {State.LOCKED, State.COOLDOWN}:
                    self._transition(State.READY if self.unlocked or self.mode == "baseline" else State.LOCKED)
                return
            if self.mode != "baseline" and not self.unlocked:
                if self.gesture not in self._activation_gestures():
                    self._reject("Interface locked; hold the activation gesture before commanding a station.", locked=True, require_release=False)
                    return
                if self._stable(self.gesture, self.settings.unlock_seconds):
                    self.unlocked = True
                    self.requires_release = True
                    self._last_activity = self.now
                    self._reset_candidate()
                    self._transition(State.READY)
                    self.reason = "Interface unlocked. Release your hand gesture before commanding."
                    self._emit("unlocked", self.reason)
                return
            if self.mode == "baseline" and not self.unlocked:
                self.unlocked = True
                self._transition(State.EXECUTING)
                self._transition(State.READY)
            if self.mode != "baseline" and self.requires_release:
                self.reason = "Release to neutral or open palm before the next command."
                key = (self.gesture, self.reason)
                if key != self._last_rejection:
                    self._emit("rejected", self.reason, "warning")
                    self._last_rejection = key
                return
            if self.mode != "baseline" and self.now < self._cooldown_until:
                self.reason = "Cooldown in progress; wait before the next command."
                return
            if self.pending:
                if self.gesture == "Pinch":
                    if self._confirm_since is None:
                        self._confirm_since = self.now
                    self.confirm_progress = min(1.0, (self.now - self._confirm_since) / self.settings.confirm_seconds)
                    if self.now - self._confirm_since + 1e-9 >= self.settings.confirm_seconds:
                        pending = dict(self.pending)
                        allowed, message = self.router.authorize(pending["action"], pending["station_id"])
                        if not allowed:
                            self._reject(message)
                            return
                        self._emit("confirmation_accepted", "Separate pinch confirmation accepted.")
                        self._execute(pending["action"], pending["station_id"], pending["source"], pending["started_at"])
                    return
                self._confirm_since = None
                self.confirm_progress = 0.0
                if self.gesture not in {"Victory", "Pointing_Up"}:
                    self.reason = "Action pending. Pinch to confirm, or open palm to cancel."
                    return
            action = GESTURE_ACTIONS.get(self.gesture)
            if action is None:
                if self.gesture != "ILoveYou":
                    self._reject("No command is mapped to this gesture.")
                return
            if self.mode != "baseline" and not self._stable(self.gesture, self.settings.hold_seconds, change_state=not bool(self.pending)):
                self.reason = f"Hold {self.gesture.replace('_', ' ')} steadily."
                return
            started_at = self._candidate_since if self._candidate_since is not None else self.now
            if action in {"next", "previous"}:
                self._select((self.factory.selected + (1 if action == "next" else -1)) % len(self.factory.stations))
                return
            station_id = self.factory.stations[self.factory.selected].id
            if self.mode == "gestureguard":
                self._preview(action, station_id, observation.source, started_at)
            else:
                self._execute(action, station_id, observation.source, started_at)

    def manual(self, action: str, station_id: str | int | None = None, *, timestamp: float | None = None, source: str = "manual") -> tuple[bool, str]:
        """Accessible explicit controls; consequential GestureGuard actions preview.

        Manual controls intentionally do not require a visible hand. Confirmation
        remains explicit; simulated stop is immediate and is never an emergency stop.
        """
        with self._lock:
            if timestamp is not None:
                self.tick(timestamp)
            self._current_source = source
            self._last_activity = self.now
            if action == "lock":
                self.lock()
                return True, self.reason
            if action == "reset":
                self.factory.reset()
                self.lock("Virtual factory reset; interface locked.")
                self._emit("factory_reset", self.reason)
                return True, self.reason
            if action == "cancel":
                self.pending = None
                self._reset_candidate()
                self._confirm_since = None
                self.confirm_progress = 0.0
                self.reason = "Pending action canceled by operator."
                self._transition(State.READY if self.unlocked or self.mode == "baseline" else State.LOCKED)
                self._emit("action_canceled", self.reason)
                return True, self.reason
            if action == "select":
                if isinstance(station_id, int):
                    index = station_id
                else:
                    index = next((i for i, item in enumerate(self.factory.stations) if item.id == station_id), -1)
                if index < 0 or index > 2:
                    return False, "Unknown workstation."
                return self._select(index)
            if action == "confirm":
                if not self.pending:
                    return False, "No pending action to confirm."
                pending = dict(self.pending)
                if pending["station_id"] != self.factory.stations[self.factory.selected].id:
                    self._reject("Selected station changed before confirmation; action canceled.")
                    return False, self.reason
                allowed, message = self.router.authorize(pending["action"], pending["station_id"])
                if not allowed:
                    self._reject(message)
                    return False, message
                self._emit("confirmation_accepted", "Manual confirmation accepted.", source="manual")
                return self._execute(pending["action"], pending["station_id"], "manual", pending["started_at"])
            if action not in {"start", "pause", "stop"}:
                return False, f"Unknown manual action: {action}"
            selected_id = str(station_id) if station_id is not None else self.factory.stations[self.factory.selected].id
            try:
                self.factory.station(selected_id)
            except ValueError as error:
                return False, str(error)
            if selected_id != self.factory.stations[self.factory.selected].id:
                self._select(next(i for i, item in enumerate(self.factory.stations) if item.id == selected_id))
            if self.mode == "gestureguard" and action != "stop":
                if self.pending:
                    return False, "Confirm or cancel the current preview first."
                return self._preview(action, selected_id, "manual")
            self.pending = None
            return self._execute(action, selected_id, "manual", self.now)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            diagnostic_candidate = self._temporal.candidate if self.mode == "gestureguard" and self.settings.temporal_filter_enabled else self._candidate
            return {"state": str(self.state), "mode": self.mode, "gesture": self.gesture,
                "score": self.score, "hold_progress": self.hold_progress,
                "confirm_progress": self.confirm_progress, "pending": dict(self.pending) if self.pending else None,
                "reason": self.reason, "selected_station": self.factory.selected,
                "requires_release": self.requires_release, "unlocked": self.unlocked,
                "settings": asdict(self.settings), "diagnostics": {"raw_gesture": self.gesture,
                    "raw_score": self.score, "filtered_gesture": self.gesture,
                    "candidate_gesture": self._candidate, "threshold": self.settings.threshold_for(self.gesture),
                    "tracking_status": "unknown", "status": "legacy_raw" if self.mode != "gestureguard" or not self.settings.temporal_filter_enabled else "waiting",
                    "hold_interruptions": self._temporal.interruptions, **self._diagnostics,
                    "candidate_gesture": diagnostic_candidate,
                    "evidence_progress": max(self.hold_progress, self.confirm_progress),
                    "unlocked": self.unlocked,
                    "activation_gesture": "Open_Palm" if self.settings.easy_demo else self.settings.activation_gesture}}
