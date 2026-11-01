"""Crossover detection (pure math), the blocker check that governs whether the real
adaptive-vs-fixed sweep may run at all, and the real evaluation adapter that wires
both scheduling policies through the authoritative assess_history() implementation.

Defect 3/4 fix (ground-truth leakage): `SweepCase` used to hand scheduling/tier
callbacks the WHOLE case, including `sans_onset_day`/`venous_onset_day` - a policy
or tier callback could read the hidden answer key while deciding what to do "today".
This module now splits every case into:

- `ObservableCase`: what a scheduling policy or the monitoring engine may see - a day
  range and, for a real (non-fixture) run, the actual AstronautDayObservation records
  up to "now". This is the ONLY thing passed to `trigger_fired_fn` and to
  `engine_tier_fn`/`make_engine_tier_fn`.
- `HiddenGroundTruth`: sans/venous onset days. Read ONLY inside `_run_policy`'s final
  metric-scoring step, after every scheduling/tier decision for the case has already
  been made - never passed to a callback.

`SweepCase` itself remains only as a convenience container pairing the two for cohort
construction; nothing in the scheduling/tier-decision path ever receives a bare
`SweepCase` any more.

Defect 3 fix (real monitoring, not a stand-in): `make_engine_tier_fn(registry)`
builds a tier_fn that calls the real `monitoring.engine.assess_history()` - the exact
same function score_crew.py uses - truncating history to "day <= now" with no
look-ahead, exactly like score_crew.py does. This is what `run_sweep` uses by
default. A caller may still pass a bare test callback for engineering-fixture tests
(see tests/test_sweep.py) - those results must never be reported as scientific
findings; `evaluate_policies.py` always uses the real engine adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from contracts.models import AstronautDayObservation, Blocker
from monitoring.engine import assess_history
from registry.loader import Registry

REQUIRED_FOR_SWEEP = {
    "fixed_schedule_interval_choice": "the fixed-schedule comparator interval",
    "hrv_trigger_assumed_accuracy": "the swept trigger-accuracy values",
    "decision_tier_thresholds": "the probability-to-tier thresholds the metrics key off of",
}


def sweep_blockers(registry: Registry) -> list[Blocker]:
    blockers = [
        Blocker(
            capability="adaptive_vs_fixed_comparison",
            blocked_by=[aid],
            message=f"Requires an approved value for {aid} ({description}).",
        )
        for aid, description in REQUIRED_FOR_SWEEP.items()
        if not registry.assumptions[aid].is_active()
    ]
    # Even granting all three above, no approved rule exists for translating an assumed
    # trigger accuracy into day-by-day firing behavior for a synthetic cohort - that
    # translation is itself an unreviewed modeling choice, not a sourced parameter, and
    # is listed unconditionally so it is never silently skipped.
    blockers.append(
        Blocker(
            capability="trigger_firing_simulation_model",
            blocked_by=[],
            message=(
                "No approved rule exists for translating an assumed trigger accuracy "
                "(e.g. 0.7) into which days a synthetic trigger actually fires. This is "
                "a simulation-design choice, not a parameter-sheet value, and needs "
                "explicit human sign-off before any sweep point can be executed."
            ),
        )
    )
    return blockers


def find_crossover(
    x_values: Sequence[float],
    policy_a_values: Sequence[float],
    policy_b_values: Sequence[float],
    lower_is_better: bool = True,
) -> Optional[float]:
    """The x (linearly interpolated between the two bracketing swept points) at which
    policy_b first overtakes policy_a, or None if no crossover occurs in-range."""
    if len(x_values) != len(policy_a_values) or len(x_values) != len(policy_b_values):
        raise ValueError("x_values, policy_a_values, policy_b_values must be the same length")
    if len(x_values) < 2:
        return None

    def margin(a: float, b: float) -> float:
        return (a - b) if lower_is_better else (b - a)  # > 0 means b is better

    margins = [margin(a, b) for a, b in zip(policy_a_values, policy_b_values)]
    for i in range(len(margins) - 1):
        d0, d1 = margins[i], margins[i + 1]
        if d0 <= 0 < d1 or (d0 < 0 <= d1):
            if d1 == d0:
                continue
            frac = -d0 / (d1 - d0)
            x0, x1 = x_values[i], x_values[i + 1]
            return x0 + frac * (x1 - x0)
    return None


@dataclass(frozen=True)
class ObservableCase:
    """Everything a scheduling policy or the monitoring engine may legitimately see.
    No onset day, no scenario label, anywhere on this type - that is the point."""

    case_id: str
    days: Sequence[int]
    # astronaut-day records available to the monitoring engine, keyed by day. May be
    # empty/partial for an engineering fixture that only exercises scheduling math.
    observations_by_day: dict[int, AstronautDayObservation] = field(default_factory=dict)

    def history_through(self, day: int) -> list[AstronautDayObservation]:
        """Observations with day <= `day`, sorted - the no-look-ahead slice that
        score_crew.py's convention also uses."""
        return [
            self.observations_by_day[d]
            for d in sorted(self.observations_by_day)
            if d <= day
        ]


@dataclass(frozen=True)
class HiddenGroundTruth:
    """Evaluation-only. Never passed to a scheduling policy or a tier_fn - only read
    inside `_run_policy` after scheduling/tier decisions already exist."""

    case_id: str
    sans_onset_day: Optional[int] = None
    venous_onset_day: Optional[int] = None

    def onset_day(self, outcome: str) -> Optional[int]:
        return self.sans_onset_day if outcome == "sans" else self.venous_onset_day


@dataclass(frozen=True)
class SweepCase:
    """Cohort-construction convenience only. Build one, then pass `.observable` to
    anything that schedules or assesses, and keep `.ground_truth` for scoring. No
    function in this module accepts a bare `SweepCase` where a decision is made."""

    observable: ObservableCase
    ground_truth: HiddenGroundTruth

    @property
    def case_id(self) -> str:
        return self.observable.case_id


@dataclass(frozen=True)
class OutcomeMetrics:
    scans_used: int
    detection_delay: Optional[int]
    missed_event: bool
    false_escalations: int
    falsely_escalated: bool  # per-astronaut boolean; see metrics.is_falsely_escalated


@dataclass(frozen=True)
class PolicyRunResult:
    policy: str  # "fixed" | "adaptive"
    per_case: dict[str, dict[str, OutcomeMetrics]]  # case_id -> outcome -> metrics

    def total_scans(self, outcome: str) -> int:
        return sum(m[outcome].scans_used for m in self.per_case.values())

    def mean_detection_delay(self, outcome: str) -> Optional[float]:
        delays = [m[outcome].detection_delay for m in self.per_case.values() if m[outcome].detection_delay is not None]
        return (sum(delays) / len(delays)) if delays else None

    def total_missed_events(self, outcome: str) -> int:
        return sum(1 for m in self.per_case.values() if m[outcome].missed_event)

    def total_false_escalations(self, outcome: str) -> int:
        """Event count (Defect 5) - see OutcomeMetrics.false_escalations."""
        return sum(m[outcome].false_escalations for m in self.per_case.values())

    def total_falsely_escalated_cases(self, outcome: str) -> int:
        """Unique-astronaut count (Defect 5) - deliberately kept separate from the
        event count above; do not confuse the two when reporting."""
        return sum(1 for m in self.per_case.values() if m[outcome].falsely_escalated)


# TierFn signature: (observable_case, scan_days_so_far, outcome) -> tier string, one
# of "monitor" | "repeat" | "consult" | "urgent" | "unresolved". Receives ONLY the
# ObservableCase - never a SweepCase, never ground truth.
TierFn = Callable[[ObservableCase, list[int], str], str]
TriggerFn = Callable[[ObservableCase, int, float], bool]


def make_engine_tier_fn(registry: Registry) -> TierFn:
    """Defect 3 fix: the real adapter. Wraps the authoritative
    `monitoring.engine.assess_history()` - the exact function score_crew.py calls -
    as a TierFn. This is what `run_sweep` uses by default; `evaluate_policies.py`
    never substitutes a test callback for this in a reported scientific result.
    """

    def _tier_fn(observable: ObservableCase, scan_days_so_far: list[int], outcome: str) -> str:
        if not scan_days_so_far:
            return "unresolved"
        as_of_day = scan_days_so_far[-1]
        history = observable.history_through(as_of_day)
        if not history:
            return "unresolved"
        result = assess_history(history, registry)
        assessment = result.sans if outcome == "sans" else result.venous
        return assessment.tier.value

    return _tier_fn


def _run_policy(
    cohort: Sequence[SweepCase],
    is_due_fn: Callable[[ObservableCase, int], bool],
    tier_fn: TierFn,
    policy_name: str,
) -> PolicyRunResult:
    from evaluation.metrics import (
        detection_delay,
        false_escalations,
        is_falsely_escalated,
        is_missed_event,
        scans_used,
    )
    from evaluation.metrics import ESCALATION_TIERS, CONSULT_OR_URGENT

    per_case: dict[str, dict[str, OutcomeMetrics]] = {}
    for case in cohort:
        observable = case.observable  # scheduling/tier decisions see only this
        scan_days: list[int] = []
        # Tracked separately per Defect 5: Repeat-or-higher (for detection/missed-event,
        # per the mission brief's "Repeat or higher" wording) vs Consult/Urgent-only
        # (for false escalations). Never merge these two lists.
        repeat_or_higher_days: dict[str, list[int]] = {"sans": [], "venous": []}
        consult_or_urgent_days: dict[str, list[int]] = {"sans": [], "venous": []}

        for day in observable.days:
            if not is_due_fn(observable, day):
                continue
            scan_days.append(day)
            for outcome in ("sans", "venous"):
                tier = tier_fn(observable, scan_days, outcome)
                if tier in ESCALATION_TIERS:
                    repeat_or_higher_days[outcome].append(day)
                if tier in CONSULT_OR_URGENT:
                    consult_or_urgent_days[outcome].append(day)

        # Ground truth is read only now, after every scheduling/tier decision above
        # has already been made without it.
        outcomes: dict[str, OutcomeMetrics] = {}
        for outcome in ("sans", "venous"):
            onset = case.ground_truth.onset_day(outcome)
            fe = false_escalations(consult_or_urgent_days[outcome], onset)
            outcomes[outcome] = OutcomeMetrics(
                scans_used=scans_used(scan_days),
                detection_delay=detection_delay(onset, repeat_or_higher_days[outcome]),
                missed_event=is_missed_event(onset, repeat_or_higher_days[outcome], observable.days[-1]),
                false_escalations=fe,
                falsely_escalated=is_falsely_escalated(consult_or_urgent_days[outcome], onset),
            )
        per_case[case.case_id] = outcomes

    return PolicyRunResult(policy=policy_name, per_case=per_case)


def run_sweep(
    accuracy_values: Sequence[float],
    cohort: Sequence[SweepCase],
    trigger_fired_fn: TriggerFn,
    fixed_interval_days: int,
    tier_fn: Optional[TierFn] = None,
    registry: Optional[Registry] = None,
) -> list[dict]:
    """Run both policies, for every swept accuracy value, over the same cohort.

    `trigger_fired_fn(observable_case, day, assumed_accuracy) -> bool` supplies the
    adaptive trigger signal and receives only the ObservableCase - never ground
    truth. `tier_fn` defaults to `make_engine_tier_fn(registry)` (the real
    `assess_history()` adapter, Defect 3's fix); pass an explicit `tier_fn` only for
    engineering-fixture tests of the scheduling/metric math, never for a reported
    scientific result. Exactly one of `tier_fn`/`registry` must be usable to build one.
    """
    from evaluation.policies import AdaptiveSchedulePolicy, FixedSchedulePolicy

    if tier_fn is None:
        if registry is None:
            raise ValueError("run_sweep requires either tier_fn (fixture) or registry (real engine adapter)")
        tier_fn = make_engine_tier_fn(registry)

    fixed_policy = FixedSchedulePolicy(interval_days=fixed_interval_days)
    adaptive_policy = AdaptiveSchedulePolicy(interval_days=fixed_interval_days)

    fixed_result = _run_policy(cohort, lambda observable, day: fixed_policy.is_scan_due(day), tier_fn, "fixed")

    points = []
    for accuracy in accuracy_values:
        adaptive_result = _run_policy(
            cohort,
            lambda observable, day, acc=accuracy: adaptive_policy.is_scan_due(
                day, trigger_fired_fn(observable, day, acc)
            ),
            tier_fn,
            "adaptive",
        )
        points.append(
            {
                "assumed_trigger_accuracy": accuracy,
                "fixed": fixed_result,
                "adaptive": adaptive_result,
            }
        )
    return points
