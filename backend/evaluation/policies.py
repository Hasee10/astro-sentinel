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
from typing import Optional, Sequence


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


@dataclass(frozen=True)
class AdaptiveReplacementSchedulePolicy:
    """ASTROSENTINEL (2026-11-04, Parts 3B/6): Option B - "defer/replace fixed
    scans based on evidence" - approved IN PRINCIPLE by Rahat, but NOT fully
    approved: see registry/design_decisions.py::
    DESIGN_DECISIONS["adaptive_scheduling_policy_semantics"].is_approved() is
    False. Must NEVER be imported or used by evaluate_policies.py's real run
    while that stays unapproved (see test_approval_checkpoint.py's dedicated
    check).

    Six sub-parameters together define Option B's full scheduling rule. Only one
    (interval_days) is independently approved (fixed_schedule_interval_choice).
    None of the other five has a default here - every one must be supplied
    explicitly at every construction site (tests only, pending approval), so none
    can be silently invented:

    1. **Maximum scan gap** (`max_gap_days`) - the hard ceiling on days since the
       last actual scan, regardless of deferral evidence. Not approved.
    2. **Lookback window** (`defer_lookback_days`) - how many days of trigger
       history count as "fresh enough" evidence to justify deferring an anchored
       scan. Previously defaulted to 3 without Rahat's sign-off - that default is
       removed here; it is exactly as unapproved as max_gap_days.
    3. **Mandatory scan behavior** - NOT implemented: whether any day/condition
       should force a scan independent of both the fixed anchor and the max-gap
       floor (e.g. a mission-start or mission-end mandatory baseline scan). No
       such rule exists in this class today.
    4. **Failed-scan retry** - NOT implemented: whether a scan that comes back
       degraded/failed (see onsd_scan_failure_rate) should trigger an earlier
       mandatory re-scan, and on what schedule. This class has no concept of scan
       quality at all - it only ever sees the boolean "was a scan taken".
    5. **Scan deferral behavior** - implemented as ONE reasonable reading (defer
       only on fresh trigger evidence, floor at max_gap_days, no rescheduling to
       a specific later day) - not necessarily the only interpretation a research
       lead might intend. Treat as a draft, not a finalized design.
    6. **Separate SANS/venous acquisition accounting** - NOT implemented: this
       class returns one boolean "is a scan due", with no per-outcome distinction.
       The shared contract also currently allows only one structured `scan` per
       astronaut-day (see handoff/research_lead/DECISIONS_NEEDED_NOW.md item 6) -
       a same-day dual SANS+venous acquisition policy is a separate, still-open
       schema question this class does not address.
    """

    interval_days: int
    max_gap_days: int  # required, no default - see docstring item 1
    defer_lookback_days: int  # required, no default - see docstring item 2 (was 3, now explicit-only)

    def __post_init__(self) -> None:
        if self.interval_days < 1:
            raise ValueError(f"interval_days must be >= 1, got {self.interval_days}")
        if self.max_gap_days < self.interval_days:
            raise ValueError(
                f"max_gap_days ({self.max_gap_days}) must be >= interval_days "
                f"({self.interval_days}) - otherwise every anchored scan would be "
                f"unconditionally forced regardless of recent trigger evidence"
            )
        if self.defer_lookback_days < 0:
            raise ValueError(f"defer_lookback_days must be >= 0, got {self.defer_lookback_days}")

    def is_scan_due(
        self,
        day: int,
        trigger_fired_today: bool,
        recent_trigger_days: Sequence[int],
        last_scan_day: Optional[int],
    ) -> bool:
        """`recent_trigger_days`: days before `day` on which the trigger fired (the
        caller's responsibility to restrict to the causally-visible past, same
        discipline as PolicyDayView). `last_scan_day`: the most recent day THIS
        policy actually scanned, or None if it never has."""
        if trigger_fired_today:
            return True

        gap_so_far = day - last_scan_day if last_scan_day is not None else day
        if gap_so_far >= self.max_gap_days:
            return True  # safety floor: never defer past the approved maximum gap

        if not _is_anchored_interval_day(day, self.interval_days):
            return False

        recently_triggered = any(day - d <= self.defer_lookback_days for d in recent_trigger_days)
        return not recently_triggered  # defer this anchor scan only if evidence is fresh
