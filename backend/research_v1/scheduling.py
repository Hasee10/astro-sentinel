"""Causal shared-session scheduler. Input type contains no latent physiology.

This is a proposed precedence, isolated behind the research gate. Fixed receives
only its anchors and one failed-acquisition retry. Adaptive replaces routine scans.
"""
from dataclasses import dataclass
from research_v1.authorization import SPEC


@dataclass(frozen=True)
class DayView:
    day: int
    last_session_day: int | None
    last_usable_session_day: int | None
    retry_due_day: int | None
    sans_tier: str
    venous_tier: str
    recent_trigger_days: tuple[int, ...]

    def __post_init__(self):
        if self.day < 1 or any(d > self.day or d < 1 for d in self.recent_trigger_days):
            raise ValueError("Future trigger observation forbidden")
        if any(d is not None and d >= self.day for d in (self.last_session_day, self.last_usable_session_day)):
            raise ValueError("Only previously acquired sessions are visible to scheduling")


def decide(view: DayView, policy: str):
    if policy not in {"fixed", "adaptive_replacement"}:
        raise ValueError("Unknown scheduling policy")
    p = SPEC["scheduling"]
    if view.day == 1:
        return True, "mission_start"
    if view.retry_due_day is not None and view.day >= view.retry_due_day:
        return True, "failed_acquisition_retry"
    if policy == "fixed":
        return ((view.day - 1) % p["routine_days"] == 0, "fixed_anchor" if (view.day - 1) % p["routine_days"] == 0 else "fixed_wait")
    gap = view.day - view.last_session_day if view.last_session_day is not None else view.day
    tiers = {view.sans_tier, view.venous_tier}
    if "urgent" in tiers and gap >= p["urgent_follow_up_days"]:
        return True, "urgent_follow_up"
    if tiers.intersection({"repeat", "consult"}) and gap >= p["repeat_consult_follow_up_days"]:
        return True, "repeat_consult_follow_up"
    if gap >= p["max_gap_days"]:
        return True, "maximum_gap"
    recent_trigger = any(0 <= view.day - d < p["trigger_lookback_days"] for d in view.recent_trigger_days)
    usable_recent = view.last_usable_session_day is not None and view.day - view.last_usable_session_day < p["trigger_lookback_days"]
    if recent_trigger and not usable_recent and gap >= p["min_trigger_gap_days"]:
        return True, "observable_trigger"
    if gap >= p["routine_days"]:
        if tiers == {"monitor"} and view.last_usable_session_day is not None and not recent_trigger:
            return False, "routine_deferred"
        return True, "routine_due"
    return False, "minimum_interval_or_no_trigger"
