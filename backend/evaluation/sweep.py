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

from contracts.models import AstronautDayObservation, Blocker, QualityStatus, ScanMeasurement, WeakSignals
from monitoring.engine import SANS_SCAN_TYPES, VENOUS_SCAN_TYPES, assess_history
from registry.design_decisions import DESIGN_DECISIONS
from registry.loader import Registry

_OUTCOME_SCAN_TYPES = {"sans": SANS_SCAN_TYPES, "venous": VENOUS_SCAN_TYPES}

REQUIRED_FOR_SWEEP = {
    "fixed_schedule_interval_choice": "the fixed-schedule comparator interval",
    "hrv_trigger_assumed_accuracy": "the swept trigger-accuracy values",
    "decision_tier_thresholds": "the probability-to-tier thresholds the metrics key off of",
}

# Issue D fix (Unified Prompt 8-9); strengthened per Unified Prompt 10-11
# section 6.3. Whether a tested trigger-firing algorithm actually exists in
# code - empty today, exactly like
# simulation.generation_models.IMPLEMENTED_GENERATION_ALGORITHMS. The blocker
# below clears ONLY when this is True AND the design decision is approved -
# never from a registry/assumption value alone, and never from a code change
# that just deletes the blocker.
#
# Flipping this to True is NOT "change a boolean" - it is a claim that ALL FIVE
# of the following are simultaneously true, and whoever flips it is asserting
# that claim:
#   1. The trigger model's definition has been approved
#      (registry/design_decisions.py::DESIGN_DECISIONS["trigger_firing_simulation_model"]).
#   2. Its numerical parameters are approved
#      (registry/data/assumptions.json::hrv_trigger_assumed_accuracy, active).
#   3. A concrete algorithm implementing that approved definition exists in code
#      (not a stub, not a TODO, not a partial branch).
#   4. That algorithm's signature actually IS a `TriggerFn` - i.e. it only
#      consumes a `PolicyDayView` and an accuracy value, nothing broader. The
#      type system already makes any other signature a TypeError at call time;
#      this point exists so a reviewer checks the algorithm was WRITTEN against
#      that contract, not merely happens to satisfy it.
#   5. Dedicated, deterministic, passing tests exist proving (3) and (4), not
#      just that `sweep_blockers()` returns an empty list.
TRIGGER_FIRING_MODEL_IMPLEMENTED: bool = True
# ASTROSENTINEL (2026-11-04): flipped alongside evaluation/trigger_model.py.
# Checking the 5-point claim above: (1) approved - design_decisions.py
# ["trigger_firing_simulation_model"].is_approved() is True. (2) approved -
# hrv_trigger_assumed_accuracy is active. (3) implemented -
# evaluation/trigger_model.py's build_trigger_schedules()/make_precomputed_trigger_fn().
# (4) signature - make_precomputed_trigger_fn() returns exactly
# Callable[[PolicyDayView, float], bool], written against that contract directly (it
# takes a PolicyDayView parameter by name and only ever reads .case_id/.day from it).
# (5) tests - tests/test_trigger_model.py (firing-probability formula, window
# boundaries, no-onset-day-access-at-call-time, determinism).

# Round-3 correction ("fix adaptive-replacement flag semantics"): whether
# run_sweep() actually has a wired, tested code path that SELECTS
# AdaptiveReplacementSchedulePolicy (evaluation/policies.py's Option B) for a
# real run - never just an authorization boolean. Today run_sweep() below
# unconditionally constructs AdaptiveSchedulePolicy (Option A, "FIXED BACKSTOP
# + TRIGGERED EXTRA SCANS") and has no policy-selection parameter at all;
# AdaptiveReplacementSchedulePolicy is never imported here. Flipping this to
# True is a claim that ALL of the following are simultaneously true:
#   1. adaptive_scheduling_policy_semantics is FULLY approved (not "in
#      principle") - registry/design_decisions.py.
#   2. run_sweep() (or an equivalent real-engine entry point) accepts an
#      explicit policy-selection parameter and actually constructs
#      AdaptiveReplacementSchedulePolicy when it is set - never a silent
#      fallback to AdaptiveSchedulePolicy while claiming otherwise.
#   3. Every one of AdaptiveReplacementSchedulePolicy's required sub-rules
#      (max_gap_days, defer_lookback_days, and the three NOT-implemented items
#      in its own docstring) has an approved, non-invented value or an
#      explicit scope decision that the missing ones are out of scope.
#   4. Dedicated, deterministic, passing tests prove the SELECTED policy is
#      the one that executes (e.g. asserting isinstance(constructed_policy,
#      AdaptiveReplacementSchedulePolicy)), not merely that an authorization
#      check returns True.
# Checked by evaluation.experiment_readiness.check_adaptive_replacement_authorized()
# ALONGSIDE (never instead of) the design-decision approval - approving the
# decision alone must never be read as "the flag now does something different".
ADAPTIVE_REPLACEMENT_EXECUTION_WIRED: bool = False


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
    # Even granting all three above, this still needs BOTH an approved design
    # decision (registry/design_decisions.py - there is no Experimental Assumption
    # slot for this, since it's a simulation-design choice, not a sourced
    # parameter) AND an implemented algorithm (TRIGGER_FIRING_MODEL_IMPLEMENTED).
    # Today neither holds, so this still fires unconditionally in practice - but
    # unlike before, approving the decision and shipping the algorithm is enough
    # to clear it with NO further code change needed here.
    decision = DESIGN_DECISIONS["trigger_firing_simulation_model"]
    if not (decision.is_approved() and TRIGGER_FIRING_MODEL_IMPLEMENTED):
        blockers.append(
            Blocker(
                capability="trigger_firing_simulation_model",
                blocked_by=[],
                message=(
                    "No approved rule exists for translating an assumed trigger accuracy "
                    "(e.g. 0.7) into which days a synthetic trigger actually fires. This is "
                    "a simulation-design choice, not a parameter-sheet value, and needs "
                    "explicit human sign-off (registry/design_decisions.py) plus an "
                    "implemented algorithm before any sweep point can be executed."
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
    No onset day, no scenario label, anywhere on this type - that is the point.

    `observations_by_day` is the underlying synthetic case's full day-by-day record
    (shared, unmodified, between the fixed and adaptive runs over the SAME cohort -
    this is what makes the two policies' comparison causally fair in the first
    place). It is NOT, by itself, safe to hand to the monitoring engine: see
    `visible_history()`.
    """

    case_id: str
    days: Sequence[int]
    # astronaut-day records available to the monitoring engine, keyed by day. May be
    # empty/partial for an engineering fixture that only exercises scheduling math.
    observations_by_day: dict[int, AstronautDayObservation] = field(default_factory=dict)

    def visible_history(self, as_of_day: int, scanned_days: set[int]) -> list[AstronautDayObservation]:
        """Issue A fix (Unified Prompt 8-9): the POLICY-SPECIFIC, causally valid
        history a scheduling policy's monitoring call may see as of `as_of_day`.

        Before this fix, `history_through(day)` returned every recorded observation
        with day <= as_of_day regardless of which days THIS policy actually
        scanned - so a scan the case data happens to carry on day 6 was visible to
        the fixed policy's day-8 assessment even though the fixed policy never
        requested a day-6 scan. Both policies share the same underlying
        `observations_by_day` (so they're evaluated on equivalent cases), but a
        day's confirmatory `scan` is only revealed here when `d in scanned_days` -
        i.e. this specific policy run actually acquired it that day. Daily
        `weak_signals` remain visible for every day <= as_of_day regardless of scan
        schedule (per the mission brief: cheap daily signals are not gated behind a
        scan decision). A day outside `scanned_days` that genuinely has no scan in
        the underlying data stays that way - this never fabricates a measurement,
        it only ever masks one that was already there but not legitimately
        requested.
        """
        visible: list[AstronautDayObservation] = []
        for d in sorted(self.observations_by_day):
            if d > as_of_day:
                continue
            obs = self.observations_by_day[d]
            if obs.scan is not None and d not in scanned_days:
                obs = obs.model_copy(update={"scan": None})
            visible.append(obs)
        return visible


@dataclass(frozen=True)
class PolicyDayView:
    """Phase 10 fix (Unified Prompt 10-11, section 4.1): the restricted, explicitly
    bounded input a scheduling TRIGGER decision may see for "today" - never the
    full `ObservableCase`. Before this type existed, `trigger_fired_fn` received
    the whole `ObservableCase`, including every future day's weak signals and
    scans - a trigger implementation could have accidentally looked ahead with
    no type-level boundary stopping it (only a comment).

    Built fresh for each day by `_build_policy_day_view()`. Contains ONLY:
    - `case_id`, `day`: identity and "today".
    - `weak_signals_by_day`: every day's weak signals with day <= today - daily
      cheap signals are never gated behind a scan decision.
    - `acquired_scans_by_day`: only scans on days < today that THIS policy run
      already scanned (its own `scanned_days_so_far`) - never today's scan
      (the decision being made is whether to request it), never a future day's,
      and never another policy run's acquisition.
    - `scanned_days_so_far`: which days < today this policy already scanned.
    - `last_known_tier`: the most recent sans/venous tier this policy computed on
      a prior scanned day, or None if it has never scanned yet - "previous
      monitoring states when available", with no re-derivation and no access to
      future information.

    Deliberately does NOT contain: any day > today's data, today's own scan
    result, any onset day, any scenario label, or another policy run's state.
    There is no field here to accidentally read any of those from - this is a
    type-level boundary, not a comment-based promise.
    """

    case_id: str
    day: int
    weak_signals_by_day: dict[int, Optional[WeakSignals]] = field(default_factory=dict)
    acquired_scans_by_day: dict[int, ScanMeasurement] = field(default_factory=dict)
    scanned_days_so_far: tuple[int, ...] = ()
    last_known_tier: dict[str, Optional[str]] = field(default_factory=lambda: {"sans": None, "venous": None})


def _build_policy_day_view(
    observable: ObservableCase,
    day: int,
    scanned_days_so_far: list[int],
    last_known_tier: dict[str, Optional[str]],
) -> PolicyDayView:
    """Builds the restricted view for deciding whether to scan on `day`. Only
    days strictly before `day` ever contribute a scan - see PolicyDayView's
    docstring. `scanned_days_so_far` and `last_known_tier` are this policy run's
    OWN state, carried forward by `_run_policy` - never another run's."""
    weak_signals_by_day: dict[int, Optional[WeakSignals]] = {}
    for d in observable.days:
        if d > day:
            continue
        obs = observable.observations_by_day.get(d)
        weak_signals_by_day[d] = obs.weak_signals if obs is not None else None

    acquired_scans_by_day: dict[int, ScanMeasurement] = {}
    prior_scanned_days = [d for d in scanned_days_so_far if d < day]
    for d in prior_scanned_days:
        obs = observable.observations_by_day.get(d)
        if obs is not None and obs.scan is not None:
            acquired_scans_by_day[d] = obs.scan

    return PolicyDayView(
        case_id=observable.case_id,
        day=day,
        weak_signals_by_day=weak_signals_by_day,
        acquired_scans_by_day=acquired_scans_by_day,
        scanned_days_so_far=tuple(prior_scanned_days),
        last_known_tier=dict(last_known_tier),
    )


@dataclass(frozen=True)
class HiddenGroundTruth:
    """Evaluation-only. Never passed to a scheduling policy or a tier_fn - only read
    inside `_run_policy` after scheduling/tier decisions already exist.

    `has_sans_event` (ASTROSENTINEL correction, 2026-11-04): carrying the onset day
    alone was not enough - a case can have `has_sans_event=True` with
    `sans_onset_day=None` (today's actual state for every SANS-event case, since
    onset-day assignment is unapproved). Treating that as indistinguishable from
    "no event" silently turned "unknown" into "confirmed zero" in missed-event/
    false-escalation accounting - see evaluation/experiment_readiness.py, which
    this field exists to make checkable before any metric is computed."""

    case_id: str
    sans_onset_day: Optional[int] = None
    venous_onset_day: Optional[int] = None
    has_sans_event: Optional[bool] = None

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
class ScanAccounting:
    """Issue C fix: 'scans used' alone conflates several different things - a
    scheduled day is not automatically a completed measurement, and the generator
    currently emits only null physiological values. This makes each stage
    explicit so the research metric's exact meaning stays transparent and can
    never silently claim a scan-count saving the underlying data doesn't support.

    `requested` is the count the legacy `scans_used` metric always meant (a day
    the policy decided a scan was due) - unchanged. The other fields are new,
    purely diagnostic engineering quantities.
    """

    requested: int             # policy decided a scan was due this day
    data_available: int        # of those, the underlying case actually has non-null scan data
    valid: int                 # of those, quality status is OK (a genuinely usable measurement)
    degraded_or_unknown: int   # quality is DEGRADED, FAILED, or UNKNOWN
    unavailable: int           # requested, but the underlying case has no scan data at all


@dataclass(frozen=True)
class OutcomeMetrics:
    scans_used: int  # UNCHANGED meaning: see ScanAccounting.requested - never redefined here
    scan_accounting: ScanAccounting
    detection_delay: Optional[int]
    missed_event: bool
    false_escalations: int
    falsely_escalated: bool  # per-astronaut boolean; see metrics.is_falsely_escalated


@dataclass(frozen=True)
class PolicyRunResult:
    policy: str  # "fixed" | "adaptive"
    per_case: dict[str, dict[str, OutcomeMetrics]]  # case_id -> outcome -> metrics

    def total_scans(self, outcome: str) -> int:
        """UNCHANGED meaning (Issue C): the 'scans used' research metric - count
        of days the policy decided a scan was due. See `total_scans_with_valid_data`
        etc. below for the new, separate engineering breakdown."""
        return sum(m[outcome].scans_used for m in self.per_case.values())

    def total_scans_with_data(self, outcome: str) -> int:
        return sum(m[outcome].scan_accounting.data_available for m in self.per_case.values())

    def total_scans_valid(self, outcome: str) -> int:
        return sum(m[outcome].scan_accounting.valid for m in self.per_case.values())

    def total_scans_degraded_or_unknown(self, outcome: str) -> int:
        return sum(m[outcome].scan_accounting.degraded_or_unknown for m in self.per_case.values())

    def total_scans_unavailable(self, outcome: str) -> int:
        """Requested but the underlying case had no scan data at all. Today this
        equals total_scans() exactly, for every case, because physiological
        generation remains blocked - a stark, honest number, not a bug."""
        return sum(m[outcome].scan_accounting.unavailable for m in self.per_case.values())

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
# of "monitor" | "repeat" | "consult" | "urgent" | "unresolved". Receives the
# ObservableCase (needed because assess_history requires the full masked history,
# not just "today") - never a SweepCase, never ground truth. Only called AFTER a
# scan has already been requested for `scan_days_so_far[-1]`, so this is not
# itself a same-day-leakage path (see IsDueFn/TriggerFn below for that boundary).
TierFn = Callable[[ObservableCase, list[int], str], str]

# TriggerFn signature (Phase 10 fix): receives ONLY a PolicyDayView - never the
# full ObservableCase, never today's own scan, never the future. This is the
# type-level fix for the temporal-leakage finding in Unified Prompt 10-11 section 4.
TriggerFn = Callable[[PolicyDayView, float], bool]

# IsDueFn signature: both policies' scheduling decision is now made from the same
# restricted PolicyDayView, built once per day regardless of policy - the fixed
# policy simply doesn't use most of it.
IsDueFn = Callable[[PolicyDayView], bool]


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
        # Issue A fix: mask out any scan the policy itself did not request - see
        # ObservableCase.visible_history's docstring.
        history = observable.visible_history(as_of_day, set(scan_days_so_far))
        if not history:
            return "unresolved"
        result = assess_history(history, registry)
        assessment = result.sans if outcome == "sans" else result.venous
        return assessment.tier.value

    return _tier_fn


def _scan_accounting(
    observable: ObservableCase, scan_days: list[int], scan_types: set
) -> ScanAccounting:
    """Issue C fix: classify each requested day's scan (if any) against the
    underlying case data - never against anything the policy could not have
    requested. `scan_types` restricts "data available" to scans relevant to the
    outcome being accounted for (SANS vs. venous), matching
    monitoring.engine's own SANS_SCAN_TYPES/VENOUS_SCAN_TYPES split.
    """
    data_available = 0
    valid = 0
    degraded_or_unknown = 0
    for day in scan_days:
        obs = observable.observations_by_day.get(day)
        scan = obs.scan if obs is not None else None
        if scan is None or scan.type not in scan_types:
            continue
        data_available += 1
        status = scan.quality.status if scan.quality is not None else None
        if status == QualityStatus.OK:
            valid += 1
        elif status in (QualityStatus.DEGRADED, QualityStatus.FAILED, QualityStatus.UNKNOWN):
            degraded_or_unknown += 1
    requested = len(scan_days)
    return ScanAccounting(
        requested=requested,
        data_available=data_available,
        valid=valid,
        degraded_or_unknown=degraded_or_unknown,
        unavailable=requested - data_available,
    )


def _run_policy(
    cohort: Sequence[SweepCase],
    is_due_fn: IsDueFn,
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
        last_known_tier: dict[str, Optional[str]] = {"sans": None, "venous": None}
        # Tracked separately per Defect 5: Repeat-or-higher (for detection/missed-event,
        # per the mission brief's "Repeat or higher" wording) vs Consult/Urgent-only
        # (for false escalations). Never merge these two lists.
        repeat_or_higher_days: dict[str, list[int]] = {"sans": [], "venous": []}
        consult_or_urgent_days: dict[str, list[int]] = {"sans": [], "venous": []}

        for day in observable.days:
            # Phase 10 fix: the scheduling decision for `day` is made from a view
            # built BEFORE that day's own scan is requested/acquired - STEP 1
            # (weak signals) then STEP 2 (decide) per section 4.2's ordering.
            day_view = _build_policy_day_view(observable, day, scan_days, last_known_tier)
            if not is_due_fn(day_view):
                continue
            scan_days.append(day)
            for outcome in ("sans", "venous"):
                tier = tier_fn(observable, scan_days, outcome)
                last_known_tier[outcome] = tier
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
                scan_accounting=_scan_accounting(observable, scan_days, _OUTCOME_SCAN_TYPES[outcome]),
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

    `trigger_fired_fn(day_view, assumed_accuracy) -> bool` supplies the adaptive
    trigger signal and receives ONLY a `PolicyDayView` (Phase 10 fix) - never the
    full `ObservableCase`, never today's own scan, never the future, never ground
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

    fixed_result = _run_policy(cohort, lambda view: fixed_policy.is_scan_due(view.day), tier_fn, "fixed")

    points = []
    for accuracy in accuracy_values:
        adaptive_result = _run_policy(
            cohort,
            lambda view, acc=accuracy: adaptive_policy.is_scan_due(
                view.day, trigger_fired_fn(view, acc)
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
