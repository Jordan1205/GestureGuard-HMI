"""Causal elapsed-time evidence and category hysteresis.

Defaults are provisional engineering settings, not fitted human-data results.
Raw scores are preserved. Moderate scores need a longer consensus hold; a bad
frame pauses evidence rather than manufacturing elapsed support during a gap.
"""
from collections import deque
from dataclasses import dataclass

from .domain import GESTURES, Observation, Settings


@dataclass(slots=True)
class FilteredEvidence:
    gesture: str = "None"
    candidate: str | None = None
    strong_seconds: float = 0.0
    supported_seconds: float = 0.0
    agreement: float = 0.0
    fresh_supported: bool = False
    fresh_strong: bool = False
    expired: bool = False
    interrupted: bool = False
    status: str = "waiting"
    started_at: float | None = None


class TemporalFilter:
    def __init__(self) -> None:
        self.interruptions = 0
        self.reset()

    def reset(self) -> None:
        self.candidate: str | None = None
        self.started_at: float | None = None
        self.strong_seconds = self.supported_seconds = 0.0
        self._last: Observation | None = None
        self._previous_supported = self._previous_strong = False
        self._interrupted_since: float | None = None
        self._challenger: str | None = None
        self._challenger_seconds = self._challenger_strong = 0.0
        self._history: deque[tuple[float, float, str | None]] = deque()

    def _clear_candidate(self) -> None:
        self.candidate = None
        self.started_at = None
        self.strong_seconds = self.supported_seconds = 0.0
        self._challenger = None
        self._challenger_seconds = self._challenger_strong = 0.0

    def update(self, observation: Observation, settings: Settings) -> FilteredEvidence:
        now, raw = observation.timestamp, observation.gesture
        previous = self._last
        dt = now - previous.timestamp if previous is not None else 0.0
        gap = previous is not None and dt > settings.max_observation_gap_seconds
        if gap:
            self._clear_candidate()
            self._history.clear()
            self._previous_supported = self._previous_strong = False
            dt = 0.0
        threshold = settings.threshold_for(raw)
        moderate_floor = min(threshold, settings.consensus_min_score)
        known = raw in GESTURES and raw != "None"
        geometry_pinch = raw == "Pinch" and observation.metadata.get("score_kind") == "geometric_quality_index" and observation.metadata.get("pinch_eligible") is True and isinstance(observation.metadata.get("pinch_ratio"), (int, float)) and observation.metadata["pinch_ratio"] <= settings.pinch_ratio
        supported = observation.hands == 1 and not observation.ambiguous and known and (geometry_pinch or observation.score >= moderate_floor)
        strong = supported and (geometry_pinch or observation.score >= threshold)
        valid_interval = previous is not None and not gap and dt > 0
        same_raw = previous is not None and previous.gesture == raw
        interval_gesture = raw if valid_interval and same_raw and supported and self._previous_supported else None
        if valid_interval:
            self._history.append((previous.timestamp, now, interval_gesture))
        cutoff = now - settings.temporal_window_seconds
        while self._history and self._history[0][1] <= cutoff:
            self._history.popleft()
        interrupted = False
        expired = gap
        status = "waiting"
        if supported and self._interrupted_since is not None and now - self._interrupted_since >= settings.instability_tolerance_seconds:
            self._clear_candidate()
            self._interrupted_since = None
            expired = True
        if supported:
            if self.candidate is None:
                self.candidate, self.started_at = raw, now
                self.strong_seconds = self.supported_seconds = 0.0
                self._interrupted_since = None
            elif raw == self.candidate:
                if same_raw and valid_interval and self._previous_supported:
                    self.supported_seconds += dt
                    if strong and self._previous_strong:
                        self.strong_seconds += dt
                self._interrupted_since = None
                self._challenger = None
                self._challenger_seconds = self._challenger_strong = 0.0
            else:
                if self._interrupted_since is None:
                    self._interrupted_since = now
                    self.interruptions += 1
                    interrupted = True
                if self._challenger != raw:
                    self._challenger = raw
                    self._challenger_seconds = self._challenger_strong = 0.0
                elif same_raw and valid_interval and self._previous_supported:
                    self._challenger_seconds += dt
                    if strong and self._previous_strong:
                        self._challenger_strong += dt
                if self._challenger_seconds + 1e-9 >= settings.switch_hold_seconds:
                    self.candidate = raw
                    self.started_at = now - self._challenger_seconds
                    self.supported_seconds = self._challenger_seconds
                    self.strong_seconds = self._challenger_strong
                    self._interrupted_since = None
                    self._challenger = None
            status = "collecting_strong_evidence" if strong else "collecting_moderate_consensus"
        else:
            if self._interrupted_since is None:
                self._interrupted_since = now
                if self.candidate is not None:
                    self.interruptions += 1
                    interrupted = True
            if now - self._interrupted_since + 1e-9 >= settings.instability_tolerance_seconds:
                expired = True
                self._clear_candidate()
                status = "sustained_tracking_loss" if observation.hands == 0 else "insufficient_evidence"
            else:
                continuity = raw == self.candidate and observation.score >= min(threshold, settings.support_score_floor)
                status = "brief_tracking_gap" if observation.hands == 0 else "brief_low_score" if continuity else "brief_classification_fluctuation"
        total = sum(end - max(start, cutoff) for start, end, _ in self._history)
        matching = sum(end - max(start, cutoff) for start, end, label in self._history if label == self.candidate)
        agreement = matching / total if total > 1e-9 else 0.0
        self._last = observation
        self._previous_supported, self._previous_strong = supported, strong
        return FilteredEvidence(gesture=self.candidate or "None", candidate=self.candidate,
            strong_seconds=self.strong_seconds, supported_seconds=self.supported_seconds,
            agreement=agreement, fresh_supported=supported and raw == self.candidate,
            fresh_strong=strong and raw == self.candidate, expired=expired,
            interrupted=interrupted, status=status, started_at=self.started_at)

    @staticmethod
    def accepted(evidence: FilteredEvidence, duration: float, settings: Settings) -> tuple[bool, str, float]:
        strong_progress = min(1.0, evidence.strong_seconds / duration)
        consensus_duration = max(settings.consensus_min_seconds, duration * settings.low_score_hold_multiplier)
        consensus_progress = min(1.0, evidence.supported_seconds / consensus_duration)
        if evidence.fresh_strong and evidence.agreement + 1e-9 >= settings.strong_consensus_ratio and strong_progress + 1e-9 >= 1:
            return True, "strong_supported_hold", strong_progress
        if evidence.fresh_supported and evidence.agreement + 1e-9 >= settings.consensus_ratio and consensus_progress + 1e-9 >= 1:
            return True, "extended_moderate_consensus", consensus_progress
        return False, "collecting", max(strong_progress, consensus_progress)
