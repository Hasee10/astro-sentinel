"""Fixed vs. adaptive measurement-scheduling policies.

Both are pure scheduling rules. Neither invents a trigger-accuracy model: the
adaptive policy only asks "did a trigger fire today?", a boolean supplied by the
caller - it does not decide, from an assumed accuracy value, when that should be
True. That mapping (accuracy -> firing behavior) is a separate, currently-unapproved
modeling choice handled (or blocked) in evaluation/sweep.py, never invented here.

Defect 6 fix - day-one anchoring convention: a scan is due on day 1 and every
`interval_days` days after that, i.e. day 1, 1+interval, 1+2*interval, ... For a
7-day interval that is days 1, 8, 15, 22, 29 (NOT 1, 7, 14, 21, 28, which the old
`day % interval_days == 0` expression produced - that gave an inconsistent 6-day
first gap). This is a pure scheduling-engineering convention; the actual interval
value remains `fixed_schedule_interval_choice`, a research-lead-approved experimental
assumption, not a newly introduced medical measurement frequency.
"""
from __future__ import annotations

from dataclasses import dataclass


def _is_anchored_interval_day(day: int, interval_days: int) -> bool:
    """True on day 1 and every `interval_days` days after day 1. Shared by both
    policies so a common fixed baseline is scheduled identically by each."""
    return day == 1 or (day - 1) % interval_days == 0


@dataclass(frozen=True)
class FixedSchedulePolicy:
    interval_days: int

    def __post_init__(self) -> None:
        if self.interval_days < 1:
            raise ValueError(f"interval_days must be >= 1, got {self.interval_days}")

    def is_scan_due(self, day: int) -> bool:
        return _is_anchored_interval_day(day, self.interval_days)


@dataclass(frozen=True)
class AdaptiveSchedulePolicy:
    """Issue B (Unified Prompt 8-9): this implements exactly ONE of several
    possible adaptive-scheduling designs - "FIXED BACKSTOP PLUS TRIGGERED SCANS".
    `is_scan_due` is a logical OR of the fixed anchor days and the trigger signal,
    so by construction this policy's scan set is always a SUPERSET of the fixed
    policy's for the same interval (see test_scheduling_policies.py's
    `test_adaptive_scan_set_is_always_a_superset_of_fixed`). It can add early
    detections; it can never use FEWER scheduled scans than the fixed comparator.
    That is not a bug - it is this specific, narrow policy's honest ceiling.

    Two other designs were explicitly NOT implemented here, because they would
    materially change what the experiment measures and need research-lead
    sign-off first (see handoff/research_lead/DECISIONS_NEEDED_NOW.md):

    - OPTION B: defer or replace some fixed-interval scans based on evidence,
      potentially reducing total scans, with explicit maximum-scan-gap and safety
      rules.
    - OPTION C: a fixed scan BUDGET reallocated to more informative days, rather
      than an unbounded backstop-plus-extra approach.

    Do not describe this class's behavior as "scan-saving" anywhere - it isn't,
    and never silently becomes Option B/C without an explicit approved redesign.
    """

    interval_days: int  # the same fixed backstop, scanned sooner if the trigger fires

    def __post_init__(self) -> None:
        if self.interval_days < 1:
            raise ValueError(f"interval_days must be >= 1, got {self.interval_days}")

    def is_scan_due(self, day: int, trigger_fired_today: bool) -> bool:
        return _is_anchored_interval_day(day, self.interval_days) or trigger_fired_today
