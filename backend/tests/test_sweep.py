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


def test_tier_fn_and_trigger_fn_receive_only_observable_case_never_sweep_case():
    """Defect 4 regression: run both policies with callbacks that assert on the
    type they received - a SweepCase (carrying ground truth) must never reach them."""
    observable = ObservableCase(case_id="A1", days=list(range(1, 11)))
    ground_truth = HiddenGroundTruth(case_id="A1", sans_onset_day=5)
    cohort = [SweepCase(observable=observable, ground_truth=ground_truth)]

    seen_types = []

    def trigger_fn(obs_case, day, acc):
        seen_types.append(type(obs_case))
        assert isinstance(obs_case, ObservableCase)
        assert not isinstance(obs_case, SweepCase)
        return False

    def tier_fn(obs_case, scan_days, outcome):
        seen_types.append(type(obs_case))
        assert isinstance(obs_case, ObservableCase)
        return "monitor"

    run_sweep(accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=trigger_fn, fixed_interval_days=7, tier_fn=tier_fn)
    assert seen_types and all(t is ObservableCase for t in seen_types)


def test_run_sweep_computes_metrics_only_after_scheduling_decisions(registry):
    """End-to-end fixture: a healthy case and a case with a red-flag event, scored
    with the REAL assess_history() adapter (Defect 3)."""
    days = list(range(1, 31))

    healthy_scan = {d: AstronautDayObservation(astronaut_id="A1", day=d, metadata=ObservationMetadata(run_id="fixture")) for d in days}

    def event_obs(d):
        scan = None
        if d == 20:
            scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=MeasurementQuality(status=QualityStatus.OK))
        return AstronautDayObservation(astronaut_id="A2", day=d, scan=scan, metadata=ObservationMetadata(run_id="fixture"))

    event_scan = {d: event_obs(d) for d in days}

    cohort = [
        SweepCase(ObservableCase("A1", days, healthy_scan), HiddenGroundTruth("A1")),
        SweepCase(ObservableCase("A2", days, event_scan), HiddenGroundTruth("A2", sans_onset_day=18)),
    ]

    def trigger_fn(observable, day, acc):
        return False  # isolate the fixed backstop for this assertion

    points = run_sweep(
        accuracy_values=[0.5],
        cohort=cohort,
        trigger_fired_fn=trigger_fn,
        fixed_interval_days=7,
        tier_fn=make_engine_tier_fn(registry),
    )
    fixed_result = points[0]["fixed"]
    # A2's red-flag day (20) is scanned under the 7-day anchor (days 1,8,15,22,29 -
    # scan day 22 is first scan day >= the red-flag day 20 that SEES it in history).
    a2_sans = fixed_result.per_case["A2"]["sans"]
    assert a2_sans.detection_delay is not None
    assert a2_sans.missed_event is False
    # Healthy A1 must show zero false escalations - there is no rule-based path to
    # Consult/Urgent for a case with no red flag and no failed/degraded scan.
    a1_sans = fixed_result.per_case["A1"]["sans"]
    assert a1_sans.false_escalations == 0
    assert a1_sans.falsely_escalated is False


def test_run_sweep_requires_tier_fn_or_registry():
    cohort = [SweepCase(ObservableCase("A1", [1]), HiddenGroundTruth("A1"))]
    with pytest.raises(ValueError):
        run_sweep(accuracy_values=[0.5], cohort=cohort, trigger_fired_fn=lambda *a: False, fixed_interval_days=7)


def test_sweep_blockers_against_real_registry_lists_all_known_gaps(registry):
    blockers = sweep_blockers(registry)
    blocked_ids = {b.capability for b in blockers}
    assert "adaptive_vs_fixed_comparison" in blocked_ids
    assert "trigger_firing_simulation_model" in blocked_ids
    # the unregistered trigger-firing model has no backing assumption id at all
    trigger_blocker = next(b for b in blockers if b.capability == "trigger_firing_simulation_model")
    assert trigger_blocker.blocked_by == []


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
