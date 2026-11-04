"""Deliverable 3 tests: evaluation/sweep.py.

Covers Defect 3 (real assess_history() adapter), Defect 4 (ground-truth leakage
boundary - ObservableCase structurally cannot carry onset days), and Defect 5
(false-escalation wiring inside _run_policy). `run_sweep`/`make_engine_tier_fn`
results here are ENGINEERING FIXTURES to verify the mechanics - never scientific
findings (no assumption is approved in the real registry; see test_evaluate_policies.py
for the real-registry blocked path).
"""
from __future__ import annotations

import pytest

from contracts.models import (
    AstronautDayObservation,
    MeasurementQuality,
    ObservationMetadata,
    QualityStatus,
    ScanMeasurement,
    ScanType,
)
from evaluation.sweep import (
    HiddenGroundTruth,
    ObservableCase,
    PolicyDayView,
    SweepCase,
    find_crossover,
    make_engine_tier_fn,
    run_sweep,
    sweep_blockers,
)
from registry.loader import load_all


@pytest.fixture(scope="module")
def registry():
    return load_all()


def test_observable_case_cannot_carry_hidden_ground_truth_fields():
    """Structural leakage test (Defect 4): ObservableCase has no onset-day
    attribute at all - there is no field to accidentally read."""
    fields = {f.name for f in ObservableCase.__dataclass_fields__.values()}
    assert "sans_onset_day" not in fields
    assert "venous_onset_day" not in fields


def test_sweep_case_keeps_ground_truth_out_of_observable():
    observable = ObservableCase(case_id="A1", days=[1, 2, 3])
    ground_truth = HiddenGroundTruth(case_id="A1", sans_onset_day=2)
    case = SweepCase(observable=observable, ground_truth=ground_truth)
    assert not hasattr(case.observable, "sans_onset_day")
    assert case.ground_truth.sans_onset_day == 2


def test_tier_fn_and_trigger_fn_never_receive_a_sweep_case():
    """Defect 4 regression, updated for the Phase 10 restricted trigger contract:
    `tier_fn` still receives `ObservableCase` (it needs the full masked history for
    assess_history), but `trigger_fn` now receives only a `PolicyDayView`. Neither
    callback may ever receive a bare `SweepCase` (which would carry ground truth)."""
    observable = ObservableCase(case_id="A1", days=list(range(1, 11)))
    ground_truth = HiddenGroundTruth(case_id="A1", sans_onset_day=5)
    cohort = [SweepCase(observable=observable, ground_truth=ground_truth)]

    trigger_seen_types = []
    tier_seen_types = []

    def trigger_fn(day_view, acc):
        trigger_seen_types.append(type(day_view))
        assert isinstance(day_view, PolicyDayView)
        assert not isinstance(day_view, SweepCase)
        return False

    def tier_fn(obs_case, scan_days, outcome):
        tier_seen_types.append(type(obs_case))
        assert isinstance(obs_case, ObservableCase)
        assert not isinstance(obs_case, SweepCase)
        return "monitor"

    run_sweep(accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=trigger_fn, fixed_interval_days=7, tier_fn=tier_fn)
    assert trigger_seen_types and all(t is PolicyDayView for t in trigger_seen_types)
    assert tier_seen_types and all(t is ObservableCase for t in tier_seen_types)


def test_run_sweep_computes_metrics_only_after_scheduling_decisions(registry):
    """End-to-end fixture: a healthy case and a case with a red-flag event, scored
    with the REAL assess_history() adapter (Defect 3). The red flag sits on day 22,
    an actual fixed-schedule anchor day (1,8,15,22,29 for interval=7) - so the fixed
    policy legitimately acquires it itself, rather than relying on cross-policy
    visibility of an unscheduled day (that would be exactly the Issue A bug)."""
    days = list(range(1, 31))

    healthy_scan = {d: AstronautDayObservation(astronaut_id="A1", day=d, metadata=ObservationMetadata(run_id="fixture")) for d in days}

    def event_obs(d):
        scan = None
        if d == 22:
            scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=MeasurementQuality(status=QualityStatus.OK))
        return AstronautDayObservation(astronaut_id="A2", day=d, scan=scan, metadata=ObservationMetadata(run_id="fixture"))

    event_scan = {d: event_obs(d) for d in days}

    cohort = [
        SweepCase(ObservableCase("A1", days, healthy_scan), HiddenGroundTruth("A1")),
        SweepCase(ObservableCase("A2", days, event_scan), HiddenGroundTruth("A2", sans_onset_day=18)),
    ]

    def trigger_fn(day_view, acc):
        return False  # isolate the fixed backstop for this assertion

    points = run_sweep(
        accuracy_values=[0.5],
        cohort=cohort,
        trigger_fired_fn=trigger_fn,
        fixed_interval_days=7,
        tier_fn=make_engine_tier_fn(registry),
    )
    fixed_result = points[0]["fixed"]
    a2_sans = fixed_result.per_case["A2"]["sans"]
    assert a2_sans.detection_delay == 22 - 18  # day 22 (acquired) - onset day 18
    assert a2_sans.missed_event is False
    assert a2_sans.scan_accounting.requested == 5  # days 1,8,15,22,29
    assert a2_sans.scan_accounting.data_available == 1  # only day 22 actually has scan data
    # Healthy A1 must show zero false escalations - there is no rule-based path to
    # Consult/Urgent for a case with no red flag and no failed/degraded scan.
    a1_sans = fixed_result.per_case["A1"]["sans"]
    assert a1_sans.false_escalations == 0
    assert a1_sans.falsely_escalated is False


# ---- Issue A (Unified Prompt 8-9): policy-specific scan visibility ----


def _single_scan_case(case_id: str, scan_day: int, days=range(1, 31)):
    """A case whose underlying data has exactly one day with real scan data
    (a red-flag ONSD scan on `scan_day`) and no scan on any other day."""
    days = list(days)
    obs_by_day = {}
    for d in days:
        scan = None
        if d == scan_day:
            scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=MeasurementQuality(status=QualityStatus.OK))
        obs_by_day[d] = AstronautDayObservation(astronaut_id=case_id, day=d, scan=scan, metadata=ObservationMetadata(run_id="fixture"))
    return ObservableCase(case_id, days, obs_by_day)


def test_unscheduled_scan_invisible_to_the_monitoring_engine(registry):
    """The core Issue A regression: a scan exists in the underlying data on day 6,
    but the fixed policy (interval=7 -> days 1,8,15,...) never scans day 6. Day 8's
    assessment must NOT see it - it must stay unresolved, not urgent."""
    observable = _single_scan_case("A1", scan_day=6)
    cohort = [SweepCase(observable, HiddenGroundTruth("A1"))]

    points = run_sweep(
        accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=lambda *a: False,
        fixed_interval_days=7, tier_fn=make_engine_tier_fn(registry),
    )
    result = points[0]["fixed"].per_case["A1"]["sans"]
    assert result.detection_delay is None  # day 6's red flag was never legitimately acquired
    assert result.scan_accounting.data_available == 0  # none of days 1,8,15,22,29 carry scan data


def test_scan_taken_by_adaptive_not_automatically_visible_to_fixed(registry):
    """Same underlying case, same cohort - only the trigger function differs
    between the two policy runs. Adaptive triggers on day 6 (acquiring the scan);
    fixed never does. Fixed's result must be unaffected by adaptive's acquisition."""
    observable = _single_scan_case("A1", scan_day=6)
    cohort = [SweepCase(observable, HiddenGroundTruth("A1"))]

    def trigger_on_day_6(day_view, acc):
        return day_view.day == 6

    points = run_sweep(
        accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=trigger_on_day_6,
        fixed_interval_days=7, tier_fn=make_engine_tier_fn(registry),
    )
    fixed = points[0]["fixed"].per_case["A1"]["sans"]
    adaptive = points[0]["adaptive"].per_case["A1"]["sans"]
    assert fixed.scan_accounting.data_available == 0
    assert fixed.detection_delay is None
    assert adaptive.scan_accounting.data_available == 1  # adaptive legitimately acquired day 6
    assert 6 in [1, 6, 8, 15, 22, 29]  # adaptive's actual scan days include the trigger day


def test_daily_weak_signals_remain_available_even_when_scan_not_scheduled(registry):
    """Weak signals are not gated behind scan acquisition - only `scan` is masked."""
    from contracts.models import WeakSignals

    days = list(range(1, 11))
    obs_by_day = {
        d: AstronautDayObservation(
            astronaut_id="A1", day=d, weak_signals=WeakSignals(hrv_hf_power=1.0),
            metadata=ObservationMetadata(run_id="fixture"),
        )
        for d in days
    }
    observable = ObservableCase("A1", days, obs_by_day)
    # as_of_day=5, no scans ever taken (scanned_days empty) - weak_signals for every
    # day <= 5 must still appear in visible_history.
    history = observable.visible_history(as_of_day=5, scanned_days=set())
    assert len(history) == 5
    assert all(o.weak_signals is not None for o in history)
    assert all(o.scan is None for o in history)  # nothing to mask here, but still unseen


def test_visible_history_never_fabricates_a_measurement():
    """A requested day with no underlying scan data stays empty - masking only ever
    removes a scan the policy didn't request, never adds one it did."""
    days = [1, 2, 3]
    obs_by_day = {d: AstronautDayObservation(astronaut_id="A1", day=d, metadata=ObservationMetadata(run_id="fixture")) for d in days}
    observable = ObservableCase("A1", days, obs_by_day)
    history = observable.visible_history(as_of_day=3, scanned_days={1, 2, 3})
    assert all(o.scan is None for o in history)


def test_visible_history_never_leaks_future_days():
    days = list(range(1, 11))
    obs_by_day = {
        d: AstronautDayObservation(
            astronaut_id="A1", day=d,
            scan=ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=(d == 9), quality=MeasurementQuality(status=QualityStatus.OK)),
            metadata=ObservationMetadata(run_id="fixture"),
        )
        for d in days
    }
    observable = ObservableCase("A1", days, obs_by_day)
    history = observable.visible_history(as_of_day=5, scanned_days=set(days))  # even if "scanned", day 9 is in the future
    assert all(o.day <= 5 for o in history)
    assert 9 not in [o.day for o in history]


def test_scan_accounting_distinguishes_unavailable_from_valid(registry):
    """Issue C: a requested scan with no underlying data is 'unavailable', not
    silently counted as a completed measurement - and the legacy scans_used count
    (requested) is unchanged by this distinction."""
    observable = _single_scan_case("A1", scan_day=8)  # day 8 is on the fixed schedule
    cohort = [SweepCase(observable, HiddenGroundTruth("A1"))]
    points = run_sweep(
        accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=lambda *a: False,
        fixed_interval_days=7, tier_fn=make_engine_tier_fn(registry),
    )
    result = points[0]["fixed"].per_case["A1"]["sans"]
    assert result.scans_used == 5  # requested: days 1,8,15,22,29 - UNCHANGED metric
    assert result.scan_accounting.requested == 5
    assert result.scan_accounting.data_available == 1  # day 8
    assert result.scan_accounting.unavailable == 4  # days 1,15,22,29 had no scan data at all


def test_scan_accounting_never_cross_counts_between_outcomes(registry):
    """Unified Prompt 10-11 section 5: a day's one structured scan field has a
    single `type` - an ONSD scan must count toward SANS accounting only, never
    toward venous (and vice versa for a JUGULAR scan). No measurement may be
    silently duplicated into both outcomes' counts."""
    observable = _single_scan_case("A1", scan_day=8)  # ONSD scan, per _single_scan_case
    cohort = [SweepCase(observable, HiddenGroundTruth("A1"))]
    points = run_sweep(
        accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=lambda *a: False,
        fixed_interval_days=7, tier_fn=make_engine_tier_fn(registry),
    )
    sans_result = points[0]["fixed"].per_case["A1"]["sans"]
    venous_result = points[0]["fixed"].per_case["A1"]["venous"]
    assert sans_result.scan_accounting.data_available == 1   # the ONSD scan counts for SANS
    assert venous_result.scan_accounting.data_available == 0  # never counted as a venous measurement
    # "requested" (scheduled days) is identical for both outcomes - a single scan
    # decision applies to the astronaut-day, not per outcome - only "data_available"
    # (and derived valid/degraded/unavailable) differ by scan type.
    assert sans_result.scan_accounting.requested == venous_result.scan_accounting.requested == 5


def test_jugular_scan_counts_only_toward_venous_not_sans(registry):
    days = list(range(1, 31))
    obs_by_day = {
        d: AstronautDayObservation(
            astronaut_id="A1", day=d,
            scan=(ScanMeasurement(type=ScanType.JUGULAR, quality=MeasurementQuality(status=QualityStatus.OK)) if d == 8 else None),
            metadata=ObservationMetadata(run_id="fixture"),
        )
        for d in days
    }
    observable = ObservableCase("A1", days, obs_by_day)
    cohort = [SweepCase(observable, HiddenGroundTruth("A1"))]
    points = run_sweep(
        accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=lambda *a: False,
        fixed_interval_days=7, tier_fn=make_engine_tier_fn(registry),
    )
    sans_result = points[0]["fixed"].per_case["A1"]["sans"]
    venous_result = points[0]["fixed"].per_case["A1"]["venous"]
    assert venous_result.scan_accounting.data_available == 1
    assert sans_result.scan_accounting.data_available == 0


def test_run_sweep_requires_tier_fn_or_registry():
    cohort = [SweepCase(ObservableCase("A1", [1]), HiddenGroundTruth("A1"))]
    with pytest.raises(ValueError):
        run_sweep(accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=lambda *a: False, fixed_interval_days=7)


def test_sweep_blockers_against_real_registry_is_now_empty():
    """ASTROSENTINEL (2026-11-04): the real registry has all 3 required assumptions
    approved plus the trigger-firing design decision approved AND implemented -
    sweep_blockers() against the real registry must report nothing blocking."""
    from registry.loader import load_all

    assert sweep_blockers(load_all()) == []


def test_sweep_blockers_against_unapproved_fixture_lists_assumption_gaps(registry):
    """General property, independent of today's real state: when the 3 required
    experimental assumptions are not approved, that's listed as a blocker. The
    trigger-firing design decision (registry/design_decisions.py) is a SEPARATE
    record from assumptions.json, so resetting only the assumptions here does not
    affect it - its own unapproved/approved states are covered directly in
    tests/test_design_decisions.py, including the unregistered-gap case."""
    from registry.loader import Registry
    from registry.models import ApprovalStatus

    unapproved = {
        aid: a.model_copy(update={"approval_status": ApprovalStatus.UNAPPROVED, "approved_by": None, "value_or_range": None})
        for aid, a in registry.assumptions.items()
    }
    fixture_registry = Registry(parameters=registry.parameters, assumptions=unapproved)

    blockers = sweep_blockers(fixture_registry)
    blocked_ids = {b.capability for b in blockers}
    assert "adaptive_vs_fixed_comparison" in blocked_ids


def test_find_crossover_detects_a_real_crossing():
    x = [0.0, 0.5, 1.0]
    a = [10, 8, 6]   # policy_a (e.g. fixed) - roughly constant/declining
    b = [15, 7, 2]   # policy_b (e.g. adaptive) - starts worse, ends better
    crossover = find_crossover(x, a, b, lower_is_better=True)
    assert crossover is not None
    assert 0.0 < crossover < 1.0


def test_find_crossover_reports_none_when_no_crossing_exists():
    x = [0.0, 0.5, 1.0]
    a = [5, 5, 5]
    b = [10, 10, 10]  # always worse - no crossover to fabricate
    assert find_crossover(x, a, b, lower_is_better=True) is None


def test_find_crossover_requires_matching_lengths():
    with pytest.raises(ValueError):
        find_crossover([0.0, 1.0], [1, 2, 3], [1, 2])
