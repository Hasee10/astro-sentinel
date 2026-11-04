"""ASTROSENTINEL: tests for evaluation/trigger_model.py - the approved windowed
trigger-firing simulation model (registry/design_decisions.py's approved
trigger_firing_simulation_model decision)."""
from __future__ import annotations

import math

import pytest

from evaluation.sweep import HiddenGroundTruth, ObservableCase, PolicyDayView
from evaluation.trigger_model import (
    POST_ONSET_WINDOW_DAYS,
    build_trigger_schedules,
    make_precomputed_trigger_fn,
    per_day_firing_probability,
)


# ---- the approved formula: h = 1 - (1-s)**(1/5) ----


def test_firing_probability_matches_approved_formula():
    for s in (0.5, 0.6, 0.7, 0.8, 0.9):
        h = per_day_firing_probability(s)
        assert h == pytest.approx(1 - (1 - s) ** (1 / 5))


def test_firing_probability_cumulative_over_window_equals_assumed_accuracy():
    """The whole point of the formula: firing independently each day at h across
    the 5-day window gives a cumulative at-least-once probability of exactly s."""
    for s in (0.5, 0.7, 0.9):
        h = per_day_firing_probability(s)
        cumulative = 1 - (1 - h) ** POST_ONSET_WINDOW_DAYS
        assert cumulative == pytest.approx(s)


def test_firing_probability_rejects_out_of_range_accuracy():
    with pytest.raises(ValueError):
        per_day_firing_probability(1.5)
    with pytest.raises(ValueError):
        per_day_firing_probability(-0.1)


def test_firing_probability_edge_cases():
    assert per_day_firing_probability(0.0) == 0.0
    assert per_day_firing_probability(1.0) == 1.0


# ---- schedule construction: window boundaries, determinism ----


def _case(case_id: str, days: list[int]) -> ObservableCase:
    return ObservableCase(case_id=case_id, days=days)


def test_schedule_fires_more_often_inside_the_post_onset_window():
    """Aggregate over many cases rather than one realization - a single case's
    5 in-window Bernoulli(h~0.63) draws can legitimately all miss (~0.7% chance),
    which would make a single-case assertion flaky, not wrong."""
    onset = 10
    cohort = [
        (_case(f"X{i}", list(range(1, 31))), HiddenGroundTruth(case_id=f"X{i}", sans_onset_day=onset))
        for i in range(300)
    ]
    schedules = build_trigger_schedules(cohort, accuracy_values=[0.9], base_false_fire_probability=0.05, seed=1)
    schedule = schedules[0.9]

    in_window_fires = sum(
        schedule[(f"X{i}", d)] for i in range(300) for d in range(onset, onset + POST_ONSET_WINDOW_DAYS)
    )
    outside_window_fires = sum(
        schedule[(f"X{i}", d)]
        for i in range(300)
        for d in range(1, 31)
        if not (onset <= d < onset + POST_ONSET_WINDOW_DAYS)
    )
    in_window_rate = in_window_fires / (300 * POST_ONSET_WINDOW_DAYS)
    outside_window_rate = outside_window_fires / (300 * (30 - POST_ONSET_WINDOW_DAYS))

    expected_h = per_day_firing_probability(0.9)
    assert in_window_rate == pytest.approx(expected_h, abs=0.05)
    assert outside_window_rate == pytest.approx(0.05, abs=0.02)
    assert in_window_rate > outside_window_rate * 5  # unambiguously higher in-window


def test_schedule_uses_only_base_rate_when_no_onset():
    gt_healthy = HiddenGroundTruth(case_id="H1", sans_onset_day=None)
    cohort = [(_case("H1", list(range(1, 31))), gt_healthy)]
    schedules = build_trigger_schedules(cohort, accuracy_values=[0.9], base_false_fire_probability=0.05, seed=2)
    schedule = schedules[0.9]
    fire_rate = sum(schedule[("H1", d)] for d in range(1, 31)) / 30
    assert fire_rate < 0.3  # nowhere near the ~63%/day in-window rate for s=0.9


def test_schedule_uses_venous_onset_never_for_the_sans_trigger():
    """TRIGGER_OUTCOME is sans - a venous-only onset must not influence firing."""
    gt = HiddenGroundTruth(case_id="V1", sans_onset_day=None, venous_onset_day=5)
    cohort = [(_case("V1", list(range(1, 31))), gt)]
    schedules = build_trigger_schedules(cohort, accuracy_values=[0.9], base_false_fire_probability=0.05, seed=2)
    schedule = schedules[0.9]
    fire_rate = sum(schedule[("V1", d)] for d in range(1, 31)) / 30
    assert fire_rate < 0.3  # treated identically to "no onset at all"


def test_schedule_deterministic_for_fixed_seed():
    gt = HiddenGroundTruth(case_id="X1", sans_onset_day=10)
    cohort = [(_case("X1", list(range(1, 31))), gt)]
    a = build_trigger_schedules(cohort, accuracy_values=[0.7], base_false_fire_probability=0.05, seed=42)
    b = build_trigger_schedules(cohort, accuracy_values=[0.7], base_false_fire_probability=0.05, seed=42)
    assert a == b


def test_schedule_covers_every_swept_accuracy_value():
    gt = HiddenGroundTruth(case_id="X1", sans_onset_day=10)
    cohort = [(_case("X1", list(range(1, 31))), gt)]
    schedules = build_trigger_schedules(
        cohort, accuracy_values=[0.5, 0.6, 0.7], base_false_fire_probability=0.05, seed=1
    )
    assert set(schedules) == {0.5, 0.6, 0.7}


# ---- the TriggerFn boundary: no onset access at call time ----


def test_precomputed_trigger_fn_signature_is_policy_day_view_and_float():
    gt = HiddenGroundTruth(case_id="X1", sans_onset_day=10)
    cohort = [(_case("X1", list(range(1, 31))), gt)]
    schedules = build_trigger_schedules(cohort, accuracy_values=[0.7], base_false_fire_probability=0.05, seed=1)
    trigger_fn = make_precomputed_trigger_fn(schedules)

    # A minimal PolicyDayView - note it carries no onset day field at all, by type.
    view = PolicyDayView(case_id="X1", day=10)
    result = trigger_fn(view, 0.7)
    assert isinstance(result, bool)
    assert not hasattr(view, "sans_onset_day")
    assert not hasattr(view, "onset_day")


def test_precomputed_trigger_fn_matches_the_schedule_exactly():
    gt = HiddenGroundTruth(case_id="X1", sans_onset_day=10)
    cohort = [(_case("X1", list(range(1, 31))), gt)]
    schedules = build_trigger_schedules(cohort, accuracy_values=[0.7], base_false_fire_probability=0.05, seed=1)
    trigger_fn = make_precomputed_trigger_fn(schedules)

    for day in range(1, 31):
        view = PolicyDayView(case_id="X1", day=day)
        assert trigger_fn(view, 0.7) == schedules[0.7][("X1", day)]


def test_precomputed_trigger_fn_defaults_to_false_for_unknown_day():
    schedules = {0.7: {("X1", 1): True}}
    trigger_fn = make_precomputed_trigger_fn(schedules)
    view = PolicyDayView(case_id="X1", day=999)
    assert trigger_fn(view, 0.7) is False


def test_precomputed_trigger_fn_raises_for_unswept_accuracy():
    schedules = {0.7: {("X1", 1): True}}
    trigger_fn = make_precomputed_trigger_fn(schedules)
    view = PolicyDayView(case_id="X1", day=1)
    with pytest.raises(KeyError):
        trigger_fn(view, 0.5)  # 0.5 was never built
