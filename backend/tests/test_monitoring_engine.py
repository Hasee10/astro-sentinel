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
    TierReason,
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
    """SANS stays blocked by name (sans_prior_mapping is approved for generation-
    layer ground truth only, never a monitoring-layer formula - see
    monitoring/engine.py's module docstring). Venous's model IS approved now, so
    with no evidence at all its explanation names the real reason: no usable
    flow-class observation, not a missing approval."""
    result = assess_history([_obs(1)], registry)
    assert "sans_prior_mapping" in str(result.sans.limitations)
    assert result.venous.probability is None
    assert "approved" in str(result.venous.limitations).lower()
    assert "flow-class" in str(result.venous.limitations).lower() or "evidence" in str(result.venous.limitations).lower()


# ---- Section 4 (Unified Prompt 8-9): tier_reason transparency ----


def test_tier_reason_distinguishes_red_flag_from_quality_from_unresolved(registry):
    red_flag_scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=_ok_quality())
    urgent = assess_history([_obs(1, scan=red_flag_scan)], registry)
    assert urgent.sans.tier_reason == TierReason.RED_FLAG_SYMPTOM

    degraded_scan = ScanMeasurement(type=ScanType.ONSD, quality=MeasurementQuality(status=QualityStatus.DEGRADED))
    repeat = assess_history([_obs(1, scan=degraded_scan)], registry)
    assert repeat.sans.tier_reason == TierReason.MEASUREMENT_QUALITY

    unresolved = assess_history([_obs(1)], registry)
    assert unresolved.sans.tier_reason == TierReason.INSUFFICIENT_EVIDENCE_FOR_PROBABILITY


def test_measurement_quality_repeat_is_never_mislabeled_as_red_flag(registry):
    """A Repeat caused by poor quality must carry tier_reason=MEASUREMENT_QUALITY,
    never RED_FLAG_SYMPTOM - the two must not be conflated downstream."""
    failed_scan = ScanMeasurement(type=ScanType.ONSD, quality=MeasurementQuality(status=QualityStatus.FAILED))
    result = assess_history([_obs(1, scan=failed_scan)], registry)
    assert result.sans.tier == TierValue.REPEAT
    assert result.sans.tier_reason != TierReason.RED_FLAG_SYMPTOM


def test_red_flag_remains_urgent_on_a_later_day_sticky_rule(registry):
    """Documents the current sticky-Urgent behavior explicitly (section 4): once a
    red flag appears, later days stay Urgent even with no new red flag - there is
    no implemented clearance/reset rule."""
    red_flag_scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=_ok_quality())
    history = [_obs(1, scan=red_flag_scan), _obs(2), _obs(3)]
    result = assess_history(history, registry)
    assert result.sans.tier == TierValue.URGENT
    assert result.sans.tier_reason == TierReason.RED_FLAG_SYMPTOM


# ---- ASTROSENTINEL (2026-11-04): the approved venous Bayesian LR model ----


def _jugular(flow_class, quality=None):
    return ScanMeasurement(
        type=ScanType.JUGULAR, jugular_flow_class=flow_class, quality=quality or _ok_quality()
    )


@pytest.mark.parametrize(
    "flow_class,expected_pct,expected_tier",
    [
        ("antegrade", 1.5544, TierValue.MONITOR),
        ("stagnant", 17.3913, TierValue.REPEAT),
        ("retrograde", 34.4828, TierValue.REPEAT),
    ],
)
def test_venous_probability_matches_hand_computed_bayes(registry, flow_class, expected_pct, expected_tier):
    """prior_odds = 0.05/0.95; posterior_odds = prior_odds * LR; posterior = odds/(1+odds).
    Values hand-computed from the approved prior (5%) and LRs (antegrade 0.3,
    stagnant 4, retrograde 10)."""
    result = assess_history([_obs(1, scan=_jugular(flow_class))], registry)
    assert result.venous.probability * 100 == pytest.approx(expected_pct, abs=0.01)
    assert result.venous.tier == expected_tier
    assert result.venous.tier_reason == TierReason.PROBABILITY_THRESHOLD
    assert result.venous.probability_label == "Simulation placeholder - unvalidated"


def test_venous_probability_never_touches_sans(registry):
    for flow_class in ("antegrade", "stagnant", "retrograde"):
        result = assess_history([_obs(1, scan=_jugular(flow_class))], registry)
        assert result.sans.probability is None
        assert result.sans.tier == TierValue.UNRESOLVED


def test_venous_uses_only_the_latest_flow_class_not_a_multiplied_history(registry):
    """No sequential multiplication of correlated daily LRs - an earlier retrograde
    reading must not inflate a later antegrade day's probability."""
    history = [_obs(1, scan=_jugular("retrograde")), _obs(5, scan=_jugular("antegrade"))]
    result = assess_history(history, registry)
    assert result.venous.probability * 100 == pytest.approx(1.5544, abs=0.01)  # antegrade alone, not compounded


def test_venous_unknown_flow_class_value_yields_no_fabricated_probability(registry):
    result = assess_history([_obs(1, scan=_jugular("not_a_real_flow_class"))], registry)
    assert result.venous.probability is None
    assert result.venous.tier == TierValue.UNRESOLVED


def test_venous_degraded_quality_reading_is_not_used_as_probability_evidence(registry):
    """An unreliable flow-class reading must fall back to the quality-Repeat rule,
    not be Bayesian-updated as if it were trustworthy evidence."""
    degraded = _jugular("retrograde", quality=MeasurementQuality(status=QualityStatus.DEGRADED))
    result = assess_history([_obs(1, scan=degraded)], registry)
    assert result.venous.probability is None
    assert result.venous.tier == TierValue.REPEAT
    assert result.venous.tier_reason == TierReason.MEASUREMENT_QUALITY


def test_stagnant_and_retrograde_never_read_below_repeat_even_with_tighter_thresholds(registry):
    """Part 3's explicit floor, exercised directly (not just relying on the
    approved numbers happening to clear the Repeat threshold already) - a fixture
    registry with a much higher Repeat threshold must still floor at Repeat."""
    from registry.loader import Registry

    tightened = registry.assumptions["decision_tier_thresholds"].model_copy(
        update={
            "value_or_range": {
                **registry.assumptions["decision_tier_thresholds"].value_or_range,
                "repeat_min_pct": 90,  # both stagnant (~17%) and retrograde (~34%) are well under this
            }
        }
    )
    fixture_registry = Registry(
        parameters=registry.parameters,
        assumptions={**registry.assumptions, "decision_tier_thresholds": tightened},
    )
    for flow_class in ("stagnant", "retrograde"):
        result = assess_history([_obs(1, scan=_jugular(flow_class))], fixture_registry)
        assert result.venous.tier == TierValue.REPEAT, flow_class


def test_decision_thresholds_sweep_changes_tier_boundaries(registry):
    """Generic threshold-application correctness, independent of the specific
    approved flow-class LRs - proves _tier_from_probability_pct's math at the
    boundaries, not just at the three real flow-class outcomes."""
    from registry.loader import Registry

    # Force a fixture jugular measure whose LR lands probability near 50%.
    custom_mapping = registry.assumptions["jugular_flow_risk_mapping"].model_copy(
        update={
            "value_or_range": {
                **registry.assumptions["jugular_flow_risk_mapping"].value_or_range,
                "flow_class_likelihood_ratios": {"antegrade": 0.3, "stagnant": 4, "retrograde": 20},
            }
        }
    )
    fixture_registry = Registry(
        parameters=registry.parameters,
        assumptions={**registry.assumptions, "jugular_flow_risk_mapping": custom_mapping},
    )
    result = assess_history([_obs(1, scan=_jugular("retrograde"))], fixture_registry)
    # prior_odds=0.05/0.95≈0.0526; LR=20 -> posterior_odds≈1.0526 -> posterior≈51.3%
    assert result.venous.probability * 100 == pytest.approx(51.28, abs=0.1)
    assert result.venous.tier == TierValue.CONSULT  # crosses the approved 40% consult threshold
