"""Small typed records shared by camera, replay, and the control engine.

Durations are monotonic seconds. Scores are classifier outputs, not calibrated
probabilities. Hand scale is a normalized image-space palm measurement.
"""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
from typing import Any


class State(StrEnum):
    LOCKED = "LOCKED"
    READY = "READY"
    GESTURE_CANDIDATE = "GESTURE_CANDIDATE"
    ACTION_PREVIEW = "ACTION_PREVIEW"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    COOLDOWN = "COOLDOWN"
    REJECTED = "REJECTED"


GESTURES = frozenset({"None", "ILoveYou", "Open_Palm", "Closed_Fist", "Thumb_Up", "Victory", "Pointing_Up", "Pinch"})
MODES = frozenset({"baseline", "protected", "gestureguard"})
GESTURE_ACTIONS = {"Thumb_Up": "start", "Closed_Fist": "pause", "Victory": "next", "Pointing_Up": "previous"}


@dataclass(slots=True)
class Observation:
    timestamp: float
    gesture: str = "None"
    score: float = 0.0
    hands: int = 0
    ambiguous: bool = False
    source: str = "simulated"
    recognition_ms: float = 0.0
    hand_scale: float | None = None
    expected_gesture: str | None = None
    intended_action: str | None = None
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Settings:
    hold_seconds: float = 0.65
    unlock_seconds: float = 1.2
    confirm_seconds: float = 0.5
    confirmation_timeout: float = 6.0
    cooldown_seconds: float = 0.8
    absence_lock_seconds: float = 3.0
    inactivity_lock_seconds: float = 30.0
    min_score: float = 0.7
    pinch_ratio: float = 0.28
    min_hand_scale: float = 0.07
    max_hand_scale: float = 0.65
    easy_demo: bool = True
    activation_gesture: str = "Open_Palm"
    temporal_filter_enabled: bool = True
    temporal_window_seconds: float = 0.35
    instability_tolerance_seconds: float = 0.22
    max_observation_gap_seconds: float = 0.30
    switch_hold_seconds: float = 0.12
    support_score_floor: float = 0.45
    consensus_min_score: float = 0.55
    consensus_ratio: float = 0.80
    strong_consensus_ratio: float = 0.65
    consensus_min_seconds: float = 0.45
    low_score_hold_multiplier: float = 1.5
    release_seconds: float = 0.15
    gesture_thresholds: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        bounds = {
            "hold_seconds": (0.1, 5), "unlock_seconds": (0.2, 5),
            "confirm_seconds": (0.1, 3), "confirmation_timeout": (1, 30),
            "cooldown_seconds": (0.1, 5), "absence_lock_seconds": (0.5, 30),
            "inactivity_lock_seconds": (5, 600), "min_score": (0.1, 1),
            "pinch_ratio": (0.05, 0.8), "min_hand_scale": (0.01, 0.8),
            "max_hand_scale": (0.02, 1.5),
            "temporal_window_seconds": (0.15, 2), "instability_tolerance_seconds": (0.05, 0.5),
            "max_observation_gap_seconds": (0.1, 1), "switch_hold_seconds": (0.05, 0.5),
            "support_score_floor": (0.1, 0.9), "consensus_min_score": (0.2, 0.95),
            "consensus_ratio": (0.6, 1), "strong_consensus_ratio": (0.5, 1), "consensus_min_seconds": (0.2, 2),
            "low_score_hold_multiplier": (1.2, 3), "release_seconds": (0.1, 1),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}.")
        if self.min_hand_scale >= self.max_hand_scale:
            raise ValueError("Minimum hand scale must be less than maximum hand scale.")
        if self.activation_gesture not in {"Open_Palm", "ILoveYou"}:
            raise ValueError("Activation gesture must be Open_Palm or ILoveYou.")
        if not isinstance(self.easy_demo, bool) or not isinstance(self.temporal_filter_enabled, bool):
            raise ValueError("Easy Demo and temporal filter settings must be booleans.")
        if self.support_score_floor > self.consensus_min_score:
            raise ValueError("Support score floor must not exceed the consensus minimum score.")
        if self.strong_consensus_ratio > self.consensus_ratio:
            raise ValueError("Strong evidence agreement must not exceed moderate consensus agreement.")
        if not isinstance(self.gesture_thresholds, dict):
            raise ValueError("Gesture thresholds must be an object of calibrated gesture scores.")
        for gesture, threshold in self.gesture_thresholds.items():
            if gesture not in GESTURES or gesture == "None" or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not .1 <= threshold <= 1:
                raise ValueError("Each calibrated gesture threshold must name a supported gesture and be 0.1–1.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def threshold_for(self, gesture: str) -> float:
        return self.gesture_thresholds.get(gesture, self.min_score)
