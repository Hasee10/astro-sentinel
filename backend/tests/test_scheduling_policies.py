"""Defect 6 regression tests: fixed-schedule day-one anchoring, across intervals
and mission lengths."""
from __future__ import annotations

import pytest

from evaluation.policies import AdaptiveSchedulePolicy, FixedSchedulePolicy


@pytest.mark.parametrize(
    "interval_days,mission_days,expected",
    [
        (7, 30, [1, 8, 15, 22, 29]),
        (5, 20, [1, 6, 11, 16]),
        (1, 5, [1, 2, 3, 4, 5]),
        (10, 25, [1, 11, 21]),
    ],
)
def test_fixed_schedule_day_one_anchoring(interval_days, mission_days, expected):
    policy = FixedSchedulePolicy(interval_days=interval_days)
    scheduled = [d for d in range(1, mission_days + 1) if policy.is_scan_due(d)]
    assert scheduled == expected


def test_fixed_schedule_old_inconsistent_convention_no_longer_produced():
    """The old `day % interval == 0` expression gave days 1,7,14,21,28 for a 7-day
    interval (an uneven first gap) - that must not be what we produce now."""
    policy = FixedSchedulePolicy(interval_days=7)
    scheduled = [d for d in range(1, 31) if policy.is_scan_due(d)]
    assert scheduled != [1, 7, 14, 21, 28]
    assert scheduled == [1, 8, 15, 22, 29]


def test_adaptive_schedule_matches_fixed_backstop_plus_triggers():
    policy = AdaptiveSchedulePolicy(interval_days=7)
    backstop_only = [d for d in range(1, 31) if policy.is_scan_due(d, trigger_fired_today=False)]
    assert backstop_only == [1, 8, 15, 22, 29]

    with_trigger_on_day_3 = [d for d in range(1, 31) if policy.is_scan_due(d, trigger_fired_today=(d == 3))]
    assert with_trigger_on_day_3 == [1, 3, 8, 15, 22, 29]


def test_both_policies_use_identical_anchoring_convention():
    fixed = FixedSchedulePolicy(interval_days=6)
    adaptive = AdaptiveSchedulePolicy(interval_days=6)
    for day in range(1, 31):
        assert fixed.is_scan_due(day) == adaptive.is_scan_due(day, trigger_fired_today=False)


@pytest.mark.parametrize("bad_interval", [0, -1, -7])
def test_rejects_non_positive_interval(bad_interval):
    with pytest.raises(ValueError):
        FixedSchedulePolicy(interval_days=bad_interval)
    with pytest.raises(ValueError):
        AdaptiveSchedulePolicy(interval_days=bad_interval)


# ---- Issue B (Unified Prompt 8-9): adaptive is "fixed backstop + triggered scans" ----
# It can only ADD scans relative to fixed, never remove or defer them. These tests
# pin that semantic down so it can never silently become Option B/C (see
# AdaptiveSchedulePolicy's docstring and handoff/research_lead/DECISIONS_NEEDED_NOW.md)
# without the tests themselves being deliberately changed.


@pytest.mark.parametrize("interval_days,mission_days", [(7, 30), (5, 20), (1, 5), (10, 25)])
def test_adaptive_scan_set_is_always_a_superset_of_fixed(interval_days, mission_days):
    fixed = FixedSchedulePolicy(interval_days=interval_days)
    adaptive = AdaptiveSchedulePolicy(interval_days=interval_days)
    fixed_days = {d for d in range(1, mission_days + 1) if fixed.is_scan_due(d)}
    # Trigger fires on an arbitrary subset of non-fixed days - still must only ADD.
    adaptive_days = {
        d for d in range(1, mission_days + 1)
        if adaptive.is_scan_due(d, trigger_fired_today=(d % 4 == 0))
    }
    assert fixed_days <= adaptive_days


def test_adaptive_can_never_schedule_fewer_scans_than_fixed_for_any_trigger_pattern():
    """However the trigger fires, adaptive_scan_count >= fixed_scan_count for the
    same interval and mission length - this is this policy's design ceiling, not
    an incidental property of one example."""
    import itertools

    interval_days, mission_days = 7, 30
    fixed = FixedSchedulePolicy(interval_days=interval_days)
    adaptive = AdaptiveSchedulePolicy(interval_days=interval_days)
    fixed_count = sum(1 for d in range(1, mission_days + 1) if fixed.is_scan_due(d))

    for trigger_days in itertools.combinations(range(1, mission_days + 1), 3):
        adaptive_count = sum(
            1 for d in range(1, mission_days + 1)
            if adaptive.is_scan_due(d, trigger_fired_today=(d in trigger_days))
        )
        assert adaptive_count >= fixed_count


def test_adaptive_scan_count_equals_fixed_when_trigger_never_fires():
    """The floor case: zero extra triggers means adaptive degenerates to exactly
    the fixed schedule - confirming "backstop" is the correct word, not "subset"."""
    interval_days, mission_days = 7, 30
    fixed = FixedSchedulePolicy(interval_days=interval_days)
    adaptive = AdaptiveSchedulePolicy(interval_days=interval_days)
    fixed_days = [d for d in range(1, mission_days + 1) if fixed.is_scan_due(d)]
    adaptive_days = [d for d in range(1, mission_days + 1) if adaptive.is_scan_due(d, trigger_fired_today=False)]
    assert fixed_days == adaptive_days
