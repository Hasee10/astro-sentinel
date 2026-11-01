"""Deliverable 2 tests: monitoring/engine.py's assess_history()."""
from __future__ import annotations

import pytest

from contracts.models import (
    AstronautDayObservation,
    MeasurementQuality,
    ObservationMetadata,
    QualityStatus,
    ScanMeasurement,
    ScanType,
    TierValue,
)
from monitoring.engine import HistoryError, assess_history
from registry.loader import load_all


@pytest.fixture(scope="module")
def registry():
    return load_all()


def _obs(day, scan=None, weak_signals=None):
    return AstronautDayObservation(
        astronaut_id="A1",
        day=day,
        weak_signals=weak_signals,
        scan=scan,
        metadata=ObservationMetadata(run_id="run-1"),
    )


def _ok_quality():
    return MeasurementQuality(status=QualityStatus.OK)


def test_no_scan_yet_is_unresolved_not_a_guess(registry):
    result = assess_history([_obs(1)], registry)
    assert result.sans.tier == TierValue.UNRESOLVED
    assert result.sans.probability is None
    assert result.venous.tier == TierValue.UNRESOLVED
    assert result.venous.probability is None


def test_red_flag_onsd_scan_escalates_sans_to_urgent_but_not_venous(registry):
    scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=_ok_quality())
    result = assess_history([_obs(1, scan=scan)], registry)
    assert result.sans.tier == TierValue.URGENT
    assert result.sans.probability is None  # rule-based escalation, never a fabricated number
    assert result.venous.tier == TierValue.UNRESOLVED  # SANS/venous independence


def test_red_flag_jugular_scan_escalates_venous_to_urgent_but_not_sans(registry):
    scan = ScanMeasurement(type=ScanType.JUGULAR, red_flag_symptom=True, quality=_ok_quality())
    result = assess_history([_obs(1, scan=scan)], registry)
    assert result.venous.tier == TierValue.URGENT
    assert result.sans.tier == TierValue.UNRESOLVED


def test_degraded_quality_scan_triggers_repeat(registry):
    scan = ScanMeasurement(type=ScanType.ONSD, quality=MeasurementQuality(status=QualityStatus.DEGRADED, reasons=["off-axis"]))
    result = assess_history([_obs(1, scan=scan)], registry)
    assert result.sans.tier == TierValue.REPEAT
    assert result.sans.probability is None


def test_failed_quality_scan_triggers_repeat(registry):
    scan = ScanMeasurement(type=ScanType.ONSD, quality=MeasurementQuality(status=QualityStatus.FAILED, reasons=["no signal"]))
    result = assess_history([_obs(1, scan=scan)], registry)
    assert result.sans.tier == TierValue.REPEAT


def test_red_flag_takes_priority_over_degraded_quality(registry):
    """Table 2's red-flag rule is unconditional - a poor-quality scan that also
    carries a red-flag symptom must still escalate to Urgent, not Repeat."""
    scan = ScanMeasurement(
        type=ScanType.ONSD, red_flag_symptom=True,
        quality=MeasurementQuality(status=QualityStatus.DEGRADED),
    )
    result = assess_history([_obs(1, scan=scan)], registry)
    assert result.sans.tier == TierValue.URGENT


def test_assess_history_uses_latest_scan_of_each_outcome_type_independently(registry):
    good_onsd = ScanMeasurement(type=ScanType.ONSD, quality=_ok_quality())
    bad_jugular = ScanMeasurement(type=ScanType.JUGULAR, quality=MeasurementQuality(status=QualityStatus.FAILED))
    result = assess_history([_obs(1, scan=good_onsd), _obs(2, scan=bad_jugular)], registry)
    assert result.sans.tier == TierValue.UNRESOLVED  # good quality, no probability model -> unresolved
    assert result.venous.tier == TierValue.REPEAT


def test_chronological_processing_no_future_leakage(registry):
    """Per score_crew.py's convention: assessing as of day 1 must never see day 2's
    red-flag event."""
    red_flag_scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=_ok_quality())
    history_through_day1 = [_obs(1)]
    result_day1 = assess_history(history_through_day1, registry)
    assert result_day1.sans.tier == TierValue.UNRESOLVED

    full_history = [_obs(1), _obs(2, scan=red_flag_scan)]
    result_day2 = assess_history(full_history, registry)
    assert result_day2.sans.tier == TierValue.URGENT
    assert result_day2.as_of_day == 2


def test_history_must_belong_to_one_astronaut(registry):
    other = AstronautDayObservation(astronaut_id="A2", day=1, metadata=ObservationMetadata(run_id="run-1"))
    with pytest.raises(HistoryError):
        assess_history([_obs(1), other], registry)


def test_history_rejects_duplicate_days(registry):
    with pytest.raises(HistoryError):
        assess_history([_obs(1), _obs(1)], registry)


def test_history_rejects_empty_list(registry):
    with pytest.raises(HistoryError):
        assess_history([], registry)


def test_unresolved_explanation_names_the_blocking_assumptions(registry):
    result = assess_history([_obs(1)], registry)
    assert "sans_prior_mapping" in str(result.sans.limitations)
    assert "venous_probability_model" in str(result.venous.limitations)
