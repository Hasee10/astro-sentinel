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
