"""Phase 10 (Unified Prompt 10-11, section 4) tests: the restricted PolicyDayView
trigger-decision contract. All data here is an ENGINEERING FIXTURE - never a
scientific finding.
"""
from __future__ import annotations

from contracts.models import (
    AstronautDayObservation,
    MeasurementQuality,
    ObservationMetadata,
    QualityStatus,
    ScanMeasurement,
    ScanType,
    WeakSignals,
)
from evaluation.sweep import (
    HiddenGroundTruth,
    ObservableCase,
    PolicyDayView,
    SweepCase,
    _build_policy_day_view,
    make_engine_tier_fn,
    run_sweep,
)
from registry.loader import load_all


def _obs(day, scan=None, weak_signals=None):
    return AstronautDayObservation(astronaut_id="A1", day=day, scan=scan, weak_signals=weak_signals, metadata=ObservationMetadata(run_id="fixture"))


def _scan(day, red_flag=False):
    return ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=red_flag, quality=MeasurementQuality(status=QualityStatus.OK))


def _case_with_full_signals_and_scans(days=range(1, 11)):
    days = list(days)
    obs_by_day = {
        d: _obs(d, scan=_scan(d, red_flag=(d == 9)), weak_signals=WeakSignals(hrv_hf_power=float(d)))
        for d in days
    }
    return ObservableCase("A1", days, obs_by_day)


def test_future_weak_signals_cannot_be_inspected():
    observable = _case_with_full_signals_and_scans()
    view = _build_policy_day_view(observable, day=5, scanned_days_so_far=[], last_known_tier={"sans": None, "venous": None})
    assert set(view.weak_signals_by_day) == {1, 2, 3, 4, 5}
    assert all(d <= 5 for d in view.weak_signals_by_day)


def test_future_scans_cannot_be_inspected():
    observable = _case_with_full_signals_and_scans()
    # Even if day 9 was somehow in scanned_days_so_far, it is still in the future
    # relative to day=5 and must not appear.
    view = _build_policy_day_view(observable, day=5, scanned_days_so_far=[1, 9], last_known_tier={"sans": None, "venous": None})
    assert 9 not in view.acquired_scans_by_day
    assert all(d < 5 for d in view.acquired_scans_by_day)


def test_same_day_scan_unavailable_before_the_request_decision():
    """The scan-request decision for day 5 must not see day 5's own scan result -
    that would let today's measurement influence whether to request itself."""
    observable = _case_with_full_signals_and_scans()
    view = _build_policy_day_view(observable, day=5, scanned_days_so_far=[1, 5], last_known_tier={"sans": None, "venous": None})
    assert 5 not in view.acquired_scans_by_day
    assert 5 not in view.scanned_days_so_far


def test_unscheduled_historical_scan_remains_invisible():
    observable = _case_with_full_signals_and_scans()
    # Day 3 has scan data in the underlying case, but this policy never scanned it.
    view = _build_policy_day_view(observable, day=5, scanned_days_so_far=[1], last_known_tier={"sans": None, "venous": None})
    assert 3 not in view.acquired_scans_by_day


def test_scheduled_previous_scan_is_visible():
    observable = _case_with_full_signals_and_scans()
    view = _build_policy_day_view(observable, day=5, scanned_days_so_far=[1, 3], last_known_tier={"sans": None, "venous": None})
    assert 1 in view.acquired_scans_by_day
    assert 3 in view.acquired_scans_by_day
    assert view.acquired_scans_by_day[1].type.value == "onsd"


def test_daily_weak_signals_remain_available_regardless_of_scan_schedule():
    observable = _case_with_full_signals_and_scans()
    view = _build_policy_day_view(observable, day=5, scanned_days_so_far=[], last_known_tier={"sans": None, "venous": None})
    assert all(view.weak_signals_by_day[d] is not None for d in range(1, 6))


def test_policy_day_view_has_no_hidden_ground_truth_fields():
    """Structural leakage test: PolicyDayView has no onset-day or scenario-label
    attribute at all - there is no field to accidentally read."""
    fields = {f.name for f in PolicyDayView.__dataclass_fields__.values()}
    assert "sans_onset_day" not in fields
    assert "venous_onset_day" not in fields
    assert "scenario_label" not in fields


def test_one_policy_cannot_see_another_policys_acquired_scans():
    """End-to-end: adaptive triggers on day 3 (acquiring a red-flag scan there);
    fixed (interval=7, never triggers) must never see it, in its own day views or
    its final assessment."""
    registry = load_all()
    days = list(range(1, 11))
    obs_by_day = {d: _obs(d, scan=(_scan(d, red_flag=True) if d == 3 else None)) for d in days}
    observable = ObservableCase("A1", days, obs_by_day)
    cohort = [SweepCase(observable, HiddenGroundTruth("A1"))]

    views_before_day_3 = []

    def trigger_on_day_3(day_view, acc):
        if day_view.day < 3:
            # No policy run has acquired day 3 itself yet at this point.
            views_before_day_3.append(set(day_view.acquired_scans_by_day))
        return day_view.day == 3

    points = run_sweep(
        accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=trigger_on_day_3,
        fixed_interval_days=7, tier_fn=make_engine_tier_fn(registry),
    )
    fixed_sans = points[0]["fixed"].per_case["A1"]["sans"]
    # fixed (interval=7 -> days 1,8) never scans day 3 - it is THIS policy's own
    # trigger function that never fires for it, so fixed never acquires day 3's
    # red-flag scan, and that must show up in its own (not adaptive's) accounting.
    assert fixed_sans.scan_accounting.data_available == 0
    # Before day 3 is reached by EITHER policy run, no view (fixed backstop days
    # are < 3 here too) may have already seen day 3's data - confirms no look-ahead.
    assert all(3 not in seen for seen in views_before_day_3)


def test_decision_independent_of_future_records_when_past_is_identical():
    """Two cases with identical history through day 5, differing only after day 5
    (one has a red flag on day 9, the other doesn't). A trigger decision made at
    day 5 must be identical for both, since it cannot see day 9 either way."""
    days = list(range(1, 11))

    def make_case(case_id, red_flag_day):
        obs_by_day = {d: _obs(d, scan=_scan(d, red_flag=(d == red_flag_day))) for d in days}
        return ObservableCase(case_id, days, obs_by_day)

    case_a = make_case("A", red_flag_day=9)
    case_b = make_case("B", red_flag_day=None)

    view_a = _build_policy_day_view(case_a, day=5, scanned_days_so_far=[1, 2, 3, 4], last_known_tier={"sans": None, "venous": None})
    view_b = _build_policy_day_view(case_b, day=5, scanned_days_so_far=[1, 2, 3, 4], last_known_tier={"sans": None, "venous": None})

    def trigger_fn(day_view, acc):
        return any(s.red_flag_symptom for s in day_view.acquired_scans_by_day.values())

    assert trigger_fn(view_a, 0.5) == trigger_fn(view_b, 0.5) == False
