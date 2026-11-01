"""Pure metric functions over day-indexed results. No clinical content lives here -
these are counting/comparison utilities that work identically on real results (once
unblocked) or on engineering fixtures used to verify the math.

Calculate separately for SANS and venous: call each function once per outcome.
"""
from __future__ import annotations

from typing import Optional, Sequence

ESCALATION_TIERS = {"repeat", "consult", "urgent"}
CONSULT_OR_URGENT = {"consult", "urgent"}


def scans_used(scan_days: Sequence[int]) -> int:
    return len(scan_days)


def detection_delay(onset_day: Optional[int], escalation_days: Sequence[int]) -> Optional[int]:
    """Days from true synthetic onset to the first qualifying escalation (Repeat or
    higher) on or after onset. None if there's no onset (healthy) or it was never
    detected - never 0 as a stand-in for "not detected"."""
    if onset_day is None:
        return None
    candidates = [d for d in escalation_days if d >= onset_day]
    if not candidates:
        return None
    return min(candidates) - onset_day


def is_missed_event(onset_day: Optional[int], escalation_days: Sequence[int], observation_end_day: int) -> bool:
    """A simulated event never escalated by the end of the observation period."""
    if onset_day is None or onset_day > observation_end_day:
        return False
    return detection_delay(onset_day, escalation_days) is None


def false_escalations(consult_or_urgent_days: Sequence[int], onset_day: Optional[int]) -> int:
    """Event count of false escalations, per the mission document's exact definition:
    a healthy synthetic astronaut (onset_day is None for this outcome) reaching
    Consult or Urgent. Repeat is NOT a false escalation under this definition - the
    caller must pass only Consult/Urgent days here (see CONSULT_OR_URGENT), never the
    broader Repeat-or-higher ESCALATION_TIERS set used for detection_delay/
    is_missed_event. Escalations in a case that does have a true onset are not counted
    here - that is a detection-delay/missed-event question, not a false escalation.

    This is an EVENT count (may be >1 for one astronaut who escalates on several
    days). See `is_falsely_escalated` for the per-astronaut boolean used to count
    unique affected astronauts - the two are deliberately not conflated."""
    if onset_day is not None:
        return 0
    return len(consult_or_urgent_days)


def is_falsely_escalated(consult_or_urgent_days: Sequence[int], onset_day: Optional[int]) -> bool:
    """Per-astronaut boolean: did this healthy case reach Consult/Urgent at all.
    Use this (summed across a cohort) to report "N unique healthy astronauts falsely
    escalated", distinct from `false_escalations`'s raw event count."""
    return false_escalations(consult_or_urgent_days, onset_day) > 0


def tier_sequence_to_days(day_tier_pairs: Sequence[tuple[int, str]], tiers: set[str]) -> list[int]:
    """Convenience: extract the days on which the tier was in `tiers` (e.g. escalation days)."""
    return [day for day, tier in day_tier_pairs if tier in tiers]
