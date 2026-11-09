"""Dense causal streams test engineering behavior, not human recognition accuracy."""
import pytest

from gestureguard.domain import Observation, Settings, State
from gestureguard.event_store import EventStore
from gestureguard.intent_engine import IntentEngine, VALID_TRANSITIONS
from gestureguard.simulation import Factory
from gestureguard.temporal_filter import TemporalFilter


class Stream:
    def __init__(self, settings=None, mode="gestureguard", step=.05):
        self.engine = IntentEngine(Factory(), EventStore(), settings or Settings(), mode=mode)
        self.time = 0.0
        self.step = step

    def hold(self, gesture, duration, score=.99, hands=1, **values):
        end = self.time + duration
        while self.time < end - 1e-9:
            self.engine.process(Observation(round(self.time, 8), gesture, score, hands, source="live", **values))
            self.time += self.step
        return self

    def unlock(self, gesture="Open_Palm"):
        self.hold(gesture, 1.35).hold("None", .25)
        assert self.engine.unlocked
        assert not self.engine.requires_release
        return self

    def preview(self, score=.99):
        self.hold("Thumb_Up", 1.1 if score < .7 else .8, score=score)
        assert self.engine.pending is not None
        return self


def commands(stream):
    return stream.engine.store.query(type="command_executed")


def test_easy_open_palm_unlocks_but_never_starts_a_station():
    stream = Stream()
    stream.hold("Open_Palm", .8)
    assert not stream.engine.unlocked
    stream.hold("Open_Palm", .55)
    assert stream.engine.unlocked
    assert stream.engine.factory.stations[0].state == "stopped"
    assert commands(stream) == []
    assert stream.engine.snapshot()["diagnostics"]["activation_gesture"] == "Open_Palm"


def test_distinct_activation_can_be_selected_without_easy_demo():
    stream = Stream(Settings(easy_demo=False, activation_gesture="ILoveYou"))
    stream.hold("Open_Palm", 2)
    assert not stream.engine.unlocked
    stream.hold("ILoveYou", 1.4)
    assert stream.engine.unlocked
    assert commands(stream) == []


def test_easy_demo_still_accepts_existing_distinct_activation():
    stream = Stream().unlock("ILoveYou")
    assert stream.engine.unlocked


def test_single_palm_blip_does_not_cancel_pending_but_deliberate_palm_does():
    stream = Stream().unlock().preview()
    stream.hold("Open_Palm", .05)
    assert stream.engine.pending is not None
    stream.hold("Pinch", .1)
    assert stream.engine.pending is not None
    stream.hold("Open_Palm", .25)
    assert stream.engine.pending is None
    assert commands(stream) == []
    assert stream.engine.state == State.READY


def test_intermittent_low_frames_pause_without_reset_or_release_latch():
    stream = Stream().unlock()
    stream.hold("Thumb_Up", .3)
    before = stream.engine.hold_progress
    stream.hold("Thumb_Up", .05, score=.48)
    assert stream.engine.hold_progress == before
    assert not stream.engine.requires_release
    stream.hold("Thumb_Up", .3)
    assert stream.engine.pending is None
    stream.hold("Thumb_Up", .05, score=.48)
    stream.hold("Thumb_Up", .25)
    assert stream.engine.pending is not None
    assert not any("quality threshold" in row["message"] for row in stream.engine.store.query(type="rejected"))
    assert stream.engine.snapshot()["diagnostics"]["hold_interruptions"] >= 2


def test_consistent_moderate_score_needs_extended_evidence_and_keeps_raw_score():
    stream = Stream().unlock()
    stream.hold("Thumb_Up", .75, score=.60)
    assert stream.engine.pending is None
    stream.hold("Thumb_Up", .4, score=.60)
    assert stream.engine.pending is not None
    diagnostics = stream.engine.snapshot()["diagnostics"]
    assert diagnostics["raw_score"] == .60
    assert diagnostics["threshold"] == .70
    assert diagnostics["acceptance_path"] == "extended_moderate_consensus"
    assert stream.engine.factory.stations[0].state == "stopped"


def test_below_consensus_floor_cannot_promote_a_command():
    stream = Stream().unlock()
    stream.hold("Thumb_Up", 3, score=.50)
    assert stream.engine.pending is None
    assert not stream.engine.requires_release
    assert commands(stream) == []
    assert "calibration" in stream.engine.reason


def test_per_gesture_calibration_is_explicit_and_does_not_lower_other_thresholds():
    settings = Settings(gesture_thresholds={"Thumb_Up": .5})
    stream = Stream(settings).unlock()
    stream.hold("Thumb_Up", .8, score=.52)
    assert stream.engine.pending is not None
    assert stream.engine.snapshot()["diagnostics"]["threshold"] == .5
    assert settings.threshold_for("Closed_Fist") == .7
    assert settings.gesture_thresholds == {"Thumb_Up": .5}


def test_brief_unknown_pauses_hold_but_does_not_count_the_gap():
    stream = Stream().unlock()
    stream.hold("Thumb_Up", .3)
    before = stream.engine.hold_progress
    stream.hold("None", .1, score=0)
    assert stream.engine.hold_progress == before
    stream.hold("Thumb_Up", .3)
    assert stream.engine.pending is None
    stream.hold("Thumb_Up", .2)
    assert stream.engine.pending is not None


def test_brief_tracking_loss_preserves_intent_but_sustained_loss_cancels_then_locks():
    stream = Stream().unlock().preview()
    stream.hold("Pinch", .25)
    stream.hold("None", .1, score=0, hands=0)
    assert stream.engine.pending is not None
    assert not stream.engine.requires_release
    stream.hold("Pinch", .2)
    assert commands(stream) == []
    stream.hold("None", .35, score=0, hands=0)
    assert stream.engine.pending is None
    assert stream.engine.unlocked
    stream.hold("None", 3, score=0, hands=0)
    assert stream.engine.state == State.LOCKED


def test_unknown_during_confirmation_cancels_without_a_new_release_requirement():
    stream = Stream().unlock().preview()
    stream.hold("None", .35, score=0)
    assert stream.engine.pending is None
    assert not stream.engine.requires_release
    stream.hold("Thumb_Up", .8)
    assert stream.engine.pending is not None


@pytest.mark.parametrize("values", [{"hands": 2}, {"ambiguous": True}])
def test_explicit_ambiguity_immediately_cancels_pending(values):
    stream = Stream().unlock().preview()
    stream.hold("Pinch", .05, **values)
    assert stream.engine.pending is None
    assert commands(stream) == []


def test_confirmation_tolerates_brief_low_sample_and_requires_actual_supported_time():
    stream = Stream().unlock().preview()
    stream.hold("Pinch", .3)
    assert stream.engine.snapshot()["diagnostics"]["candidate_gesture"] == "Pinch"
    before = stream.engine.confirm_progress
    stream.hold("Pinch", .1, score=.48)
    assert stream.engine.confirm_progress == before
    stream.hold("Pinch", .2)
    assert commands(stream) == []
    stream.hold("Pinch", .2)
    assert len(commands(stream)) == 1
    assert stream.engine.factory.stations[0].state == "running"


def test_moderate_confirmation_still_requires_a_separate_extended_hold():
    stream = Stream().unlock().preview(score=.6)
    stream.hold("Thumb_Up", .8, score=.6)
    assert commands(stream) == []
    stream.hold("Pinch", .55, score=.6)
    assert commands(stream) == []
    stream.hold("Pinch", .5, score=.6)
    assert len(commands(stream)) == 1


def test_release_after_execution_is_not_satisfied_by_short_loss_or_unknown():
    stream = Stream().unlock().preview()
    stream.hold("Pinch", .7)
    assert len(commands(stream)) == 1
    assert stream.engine.requires_release
    stream.hold("None", .1, score=0, hands=0)
    stream.hold("None", .2, score=0)
    stream.hold("Closed_Fist", 1)
    assert stream.engine.requires_release
    assert len(commands(stream)) == 1
    stream.hold("Open_Palm", .25)
    assert not stream.engine.requires_release
    stream.hold("Closed_Fist", .8).hold("Pinch", .7)
    assert len(commands(stream)) == 2
    assert stream.engine.factory.stations[0].state == "paused"


def test_missing_samples_do_not_coast_across_a_large_timestamp_gap():
    stream = Stream().unlock()
    stream.hold("Thumb_Up", .4)
    stream.time += 1
    stream.hold("Thumb_Up", .05)
    assert stream.engine.pending is None
    assert stream.engine.hold_progress == 0


def test_geometry_pinch_uses_geometry_gate_not_classifier_threshold():
    stream = Stream(Settings(min_score=.9)).unlock().preview()
    metadata = {"score_kind": "geometric_quality_index", "pinch_ratio": .25, "pinch_eligible": True}
    stream.hold("Pinch", .7, score=.1, metadata=metadata)
    assert len(commands(stream)) == 1
    diagnostics = stream.engine.snapshot()["diagnostics"]
    assert diagnostics["raw_score"] == .1
    assert diagnostics["threshold_kind"] == "maximum_normalized_tip_distance"
    assert diagnostics["threshold"] == .28
    assert diagnostics["classifier_threshold"] == .9


def test_geometry_diagnostics_preserve_the_actual_pretrained_classifier_output():
    stream = Stream().unlock().preview()
    metadata = {"score_kind": "geometric_quality_index", "pinch_ratio": .2,
                "pinch_eligible": True, "raw_canned_gesture": "None", "raw_canned_score": .32}
    stream.hold("Pinch", .1, score=.28, metadata=metadata)
    diagnostic = stream.engine.snapshot()["diagnostics"]
    assert diagnostic["raw_gesture"] == "None"
    assert diagnostic["raw_score"] == .32
    assert diagnostic["interpreted_gesture"] == "Pinch"
    assert diagnostic["interpreted_score"] == .28
    assert diagnostic["score_kind"] == "classifier_output"
    assert diagnostic["interpreted_score_kind"] == "geometric_quality_index"


def test_filtered_full_lifecycle_only_uses_valid_state_transitions():
    stream = Stream().unlock().preview()
    stream.hold("Pinch", .7).hold("Open_Palm", .25)
    stream.hold("Victory", .8)
    for event in stream.engine.store.query(type="state_changed"):
        detail = event["details"]
        assert State(detail["state"]) in VALID_TRANSITIONS[State(detail["previous"])]


def test_filter_hysteresis_retains_a_candidate_across_a_short_category_blip():
    temporal, settings = TemporalFilter(), Settings()
    for timestamp in (0, .05, .10, .15, .20):
        evidence = temporal.update(Observation(timestamp, "Thumb_Up", .9, 1), settings)
    assert evidence.candidate == "Thumb_Up"
    evidence = temporal.update(Observation(.25, "Victory", .9, 1), settings)
    assert evidence.candidate == "Thumb_Up"
    assert not evidence.fresh_supported
    evidence = temporal.update(Observation(.30, "Thumb_Up", .9, 1), settings)
    assert evidence.candidate == "Thumb_Up"
    assert evidence.strong_seconds == pytest.approx(.2)


def test_disconnected_strong_bursts_cannot_accumulate_into_a_command_without_recent_coherence():
    stream = Stream().unlock()
    for _ in range(15):
        stream.hold("Thumb_Up", .1, score=.9).hold("Thumb_Up", .1, score=.48)
    assert stream.engine.pending is None
    assert commands(stream) == []
    assert stream.engine.snapshot()["diagnostics"]["consensus_agreement"] < .65


def test_settings_reject_invalid_temporal_and_calibration_configuration():
    for values in ({"easy_demo": "yes"}, {"gesture_thresholds": {"Thumb_Up": 1.2}}, {"gesture_thresholds": {"Wrong": .6}}, {"consensus_ratio": .3}, {"support_score_floor": .8}, {"activation_gesture": "Thumb_Up"}):
        with pytest.raises(ValueError):
            Settings(**values)


def test_raw_logged_observations_reproduce_the_improved_engine_exactly():
    stream = Stream().unlock()
    stream.hold("Thumb_Up", .3).hold("Thumb_Up", .1, score=.48)
    stream.hold("Thumb_Up", .6).hold("Pinch", .3)
    stream.hold("None", .1, score=0, hands=0).hold("Pinch", .5)
    replay = IntentEngine(Factory(), EventStore(), Settings())
    observations = stream.engine.store.query(limit=200000, type="input_observation")
    for event in reversed(observations):
        replay.process(Observation(**event["details"]))
    assert replay.snapshot() == stream.engine.snapshot()
    assert replay.factory.snapshot() == stream.engine.factory.snapshot()
    original_commands = stream.engine.store.query(type="command_executed")
    replay_commands = replay.store.query(type="command_executed")
    assert len(original_commands) == len(replay_commands) == 1
    assert original_commands[0]["details"] == replay_commands[0]["details"]
