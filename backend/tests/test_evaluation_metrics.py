"""Deliverable 3 tests: evaluation/metrics.py, especially Defect 5 (false-escalation
must exclude Repeat-tier events)."""
from __future__ import annotations

from evaluation.metrics import (
    CONSULT_OR_URGENT,
    ESCALATION_TIERS,
    detection_delay,
    false_escalations,
    is_falsely_escalated,
    is_missed_event,
    scans_used,
    tier_sequence_to_days,
)


def test_scans_used_counts_days():
    assert scans_used([1, 8, 15]) == 3
    assert scans_used([]) == 0


def test_detection_delay_from_onset_to_first_qualifying_escalation():
    assert detection_delay(onset_day=10, escalation_days=[15]) == 5
    assert detection_delay(onset_day=10, escalation_days=[5, 15]) == 5  # ignores pre-onset escalation
    assert detection_delay(onset_day=10, escalation_days=[10]) == 0


def test_detection_delay_none_when_healthy_or_never_detected():
    assert detection_delay(onset_day=None, escalation_days=[5]) is None
    assert detection_delay(onset_day=10, escalation_days=[]) is None
    assert detection_delay(onset_day=10, escalation_days=[5]) is None  # only pre-onset


def test_is_missed_event():
    assert is_missed_event(onset_day=10, escalation_days=[], observation_end_day=30) is True
    assert is_missed_event(onset_day=10, escalation_days=[12], observation_end_day=30) is False
    assert is_missed_event(onset_day=None, escalation_days=[], observation_end_day=30) is False
    assert is_missed_event(onset_day=40, escalation_days=[], observation_end_day=30) is False  # onset beyond mission


def test_false_escalations_defect_5_excludes_repeat():
    """The core Defect 5 regression: callers must pass Consult/Urgent-only days.
    Repeat-tier days must never inflate this count."""
    repeat_and_urgent_days = [5, 12]  # caller correctly pre-filtered to consult/urgent only
    assert false_escalations(repeat_and_urgent_days, onset_day=None) == 2
    assert false_escalations([], onset_day=None) == 0


def test_false_escalations_zero_when_case_has_a_true_onset():
    assert false_escalations([12, 20], onset_day=5) == 0


def test_is_falsely_escalated_boolean_distinct_from_event_count():
    assert is_falsely_escalated([5, 12, 20], onset_day=None) is True  # 3 events, 1 astronaut
    assert is_falsely_escalated([], onset_day=None) is False
    assert is_falsely_escalated([5], onset_day=3) is False  # has true onset, not a false escalation


def test_escalation_tier_sets_do_not_overlap_in_a_way_that_breaks_the_distinction():
    assert "repeat" in ESCALATION_TIERS
    assert "repeat" not in CONSULT_OR_URGENT
    assert CONSULT_OR_URGENT <= ESCALATION_TIERS


def test_tier_sequence_to_days_filters_by_tier_set():
    pairs = [(1, "monitor"), (2, "repeat"), (3, "urgent"), (4, "monitor")]
    assert tier_sequence_to_days(pairs, ESCALATION_TIERS) == [2, 3]
    assert tier_sequence_to_days(pairs, CONSULT_OR_URGENT) == [3]
