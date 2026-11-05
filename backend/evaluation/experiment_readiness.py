"""Preflight experiment-readiness check (ASTROSENTINEL correction, 2026-11-04;
extended same day - "approving onset timing alone cannot produce an apparently
valid full experiment").

`evaluation.sweep.sweep_blockers()` checks whether the right ASSUMPTIONS/DECISIONS
are approved - necessary, but not sufficient. The first version of this module
added one more check: is the ground-truth DATA on hand self-consistent (no
has_sans_event=True, sans_onset_day=None cases)? That caught the original defect
(unknown onset silently scored as zero missed events) but was itself incomplete -
onset-day consistency alone says nothing about whether a physiological PROGRESSION
exists to detect, whether the MONITORING engine has a rule to detect it with, or
whether venous has anything beyond onset timing blocking it. This module now checks
all of that, each one independently capable of blocking the experiment on its own:

1. Ground-truth onset/event consistency (original check).
2. Physiological progression capability - via the existing generation-model
   readiness system (simulation.generation_models), never a new ad-hoc flag.
3. Monitoring-rule authorization per outcome - via the existing
   monitoring.engine.MONITORING_PROBABILITY_IMPLEMENTED set.
4. For venous specifically: event-occurrence model, onset model, AND
   measurement-generation, named and checked separately, so a partial fix to
   just one of the three is visible as such, never read as "venous is ready".
5. Adaptive-replacement-policy authorization, only checked when explicitly
   requested (nothing in this codebase requests it today - see
   evaluation/policies.py::AdaptiveReplacementSchedulePolicy).
6. An opt-in, explicitly-labeled SANS-only pilot mode that never activates by
   default and never silently presents partial results as the full study.

No new numerical parameter is introduced anywhere in this module - every check
reads an existing registry/design-decision/readiness state, never a value this
module itself invents.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from contracts.models import Blocker
from evaluation.sweep import HiddenGroundTruth, SweepCase
from registry.design_decisions import DESIGN_DECISIONS
from registry.loader import Registry
from simulation.generation_models import GENERATION_MODEL_SPECS, ModelReadiness, check_readiness

SANS_ONLY_PILOT_LABEL = "SANS-ONLY PILOT EVALUATION - PARTIAL STUDY, VENOUS OUTCOME EXCLUDED"


class EventGroundTruthStatus(str, Enum):
    """Purely about whether the SIMULATION's own synthetic ground truth is complete
    enough to score against, for one outcome, one case - never a medical diagnosis,
    never read by anything other than this module and its tests."""

    CONFIRMED_NONE = "confirmed_none"  # no synthetic event - a genuine "healthy" case for this outcome
    CONFIRMED_WITH_ONSET = "confirmed_with_onset"  # event occurred AND onset day is assigned
    EVENT_UNKNOWN_ONSET = "event_unknown_onset"  # event flagged, onset day NOT assigned - today's real SANS state
    UNDETERMINED = "undetermined"  # no event-occurrence model exists for this outcome at all (today: venous)


def sans_ground_truth_status(gt: HiddenGroundTruth) -> EventGroundTruthStatus:
    if gt.has_sans_event is None:
        return EventGroundTruthStatus.UNDETERMINED
    if gt.has_sans_event is False:
        if gt.sans_onset_day is not None:
            # Inconsistent synthetic data (no event, but an onset day exists) -
            # flagged rather than silently trusting either field over the other.
            return EventGroundTruthStatus.UNDETERMINED
        return EventGroundTruthStatus.CONFIRMED_NONE
    return (
        EventGroundTruthStatus.CONFIRMED_WITH_ONSET
        if gt.sans_onset_day is not None
        else EventGroundTruthStatus.EVENT_UNKNOWN_ONSET
    )


def venous_ground_truth_status(gt: HiddenGroundTruth) -> EventGroundTruthStatus:
    """No venous event-occurrence model is approved at all ("Do not invent venous
    event prevalence") - every venous case is UNDETERMINED regardless of
    `venous_onset_day` or `scenario_label`, neither of which is an approved
    ground-truth signal for whether a venous event actually occurs."""
    return EventGroundTruthStatus.UNDETERMINED


GROUND_TRUTH_STATUS_FN = {"sans": sans_ground_truth_status, "venous": venous_ground_truth_status}

_UNRESOLVED_STATUSES = {EventGroundTruthStatus.EVENT_UNKNOWN_ONSET, EventGroundTruthStatus.UNDETERMINED}

# Which generation-model capability, if any, represents "a progression/measurement
# chain exists for this outcome" - reused, never duplicated, from
# simulation.generation_models.GENERATION_MODEL_SPECS. venous has no dedicated
# progression entry: jugular_scan_values already covers its whole, currently
# entirely-unimplemented measurement chain (baseline AND progression together).
_PROGRESSION_CAPABILITY = {"sans": "sans_physiological_progression", "venous": "jugular_scan_values"}

# monitoring.engine.MONITORING_PROBABILITY_IMPLEMENTED duplicated here as a string
# constant would risk drifting out of sync - imported directly instead, below.


@dataclass(frozen=True)
class CohortGroundTruthSummary:
    outcome: str
    counts: dict[str, int]  # EventGroundTruthStatus.value -> count

    @property
    def is_fully_resolved(self) -> bool:
        """True only if every case is CONFIRMED_NONE or CONFIRMED_WITH_ONSET - i.e.
        detection-delay/missed-event/false-escalation metrics are meaningful for the
        WHOLE cohort, not silently correct for a subset and wrong for the rest."""
        return all(self.counts.get(status.value, 0) == 0 for status in _UNRESOLVED_STATUSES)


def summarize_ground_truth(cohort: Sequence[SweepCase], outcome: str) -> CohortGroundTruthSummary:
    status_fn = GROUND_TRUTH_STATUS_FN[outcome]
    counts: dict[str, int] = {}
    for case in cohort:
        status = status_fn(case.ground_truth)
        counts[status.value] = counts.get(status.value, 0) + 1
    return CohortGroundTruthSummary(outcome=outcome, counts=counts)


def _progression_capability_ready(outcome: str, registry: Registry) -> tuple[bool, str]:
    """Reuses simulation.generation_models.check_readiness() directly - never a
    second, parallel readiness concept. Returns (ready, human-readable state)."""
    capability = _PROGRESSION_CAPABILITY[outcome]
    result = check_readiness(GENERATION_MODEL_SPECS[capability], registry)
    return result.state == ModelReadiness.READY, f"{capability}={result.state.value}"


def _monitoring_rule_ready(outcome: str) -> bool:
    """Reuses monitoring.engine.MONITORING_PROBABILITY_IMPLEMENTED directly - the
    one place that already tracks which outcomes have a real evidence-to-tier
    formula (see that module's own extensive docstring on why sans_prior_mapping's
    approval does NOT put "sans" in this set)."""
    from monitoring.engine import MONITORING_PROBABILITY_IMPLEMENTED

    return outcome in MONITORING_PROBABILITY_IMPLEMENTED


def _venous_specific_status(registry: Registry) -> dict[str, bool]:
    """The three conditions Part 4 names explicitly, checked and reported
    separately so a partial fix to just one is visible as such."""
    event_model = DESIGN_DECISIONS.get("venous_event_occurrence_model")
    onset_model = DESIGN_DECISIONS.get("sans_venous_onset_day_assignment")
    measurement_ready, _ = _progression_capability_ready("venous", registry)
    return {
        "event_occurrence_model_approved": bool(event_model and event_model.is_approved()),
        "onset_model_approved": bool(onset_model and onset_model.is_approved()),
        "measurement_generation_implemented": measurement_ready,
    }


def check_adaptive_replacement_authorized(registry: Registry) -> tuple[bool, Optional[Blocker]]:
    """Part 5, extended (round-3 correction - "do not merely flip an approval
    boolean"): Option B (AdaptiveReplacementSchedulePolicy) requires BOTH:

    (a) adaptive_scheduling_policy_semantics FULLY approved (not the "in
        principle" partial state it carries today), AND
    (b) evaluation.sweep.ADAPTIVE_REPLACEMENT_EXECUTION_WIRED - an actual,
        tested code path that SELECTS AdaptiveReplacementSchedulePolicy for a
        real run. `run_sweep()` today unconditionally constructs
        AdaptiveSchedulePolicy (Option A, "FIXED BACKSTOP + TRIGGERED EXTRA
        SCANS") and has no policy-selection parameter at all - approving (a)
        alone would not change what actually executes, which is exactly the
        false "scan-saving" claim this check exists to prevent. See that
        module-level constant's own docstring for the full claim flipping it
        would make.

    This is the same approved-AND-implemented discipline used everywhere else
    in this codebase (e.g. TRIGGER_FIRING_MODEL_IMPLEMENTED), applied here so
    a future approval of (a) alone can never silently make the CLI flag appear
    authorized while the old policy keeps running underneath it. Nothing in
    this codebase calls this with intent to activate Option B today; see
    check_experiment_readiness's `use_adaptive_replacement`.
    """
    from evaluation.sweep import ADAPTIVE_REPLACEMENT_EXECUTION_WIRED

    decision = DESIGN_DECISIONS.get("adaptive_scheduling_policy_semantics")
    decision_approved = bool(decision is not None and decision.is_approved())
    if decision_approved and ADAPTIVE_REPLACEMENT_EXECUTION_WIRED:
        return True, None

    unmet: list[str] = []
    if not decision_approved:
        unmet.append(
            "adaptive_scheduling_policy_semantics is not fully approved (today "
            "only 'in principle' - max_gap_days, defer_lookback_days, and the "
            "remaining sub-rules in AdaptiveReplacementSchedulePolicy's "
            "docstring are still unspecified)"
        )
    if not ADAPTIVE_REPLACEMENT_EXECUTION_WIRED:
        unmet.append(
            "no wired, tested execution path selects AdaptiveReplacementSchedulePolicy "
            "for a real run - evaluation.sweep.run_sweep() always constructs the "
            "original AdaptiveSchedulePolicy (FIXED BACKSTOP + TRIGGERED EXTRA "
            "SCANS) today, regardless of this flag"
        )
    return False, Blocker(
        capability="adaptive_replacement_scheduling",
        blocked_by=[],
        message=(
            "AdaptiveReplacementSchedulePolicy (Option B) requires BOTH a full "
            "design-decision approval AND a wired, tested execution path before "
            "it may run - approving the decision alone would not change what "
            "executes. Unmet: " + "; ".join(unmet) + ". This blocker fires only "
            "because Option B was explicitly requested; it is never used by "
            "default, and the original policy (FIXED BACKSTOP + TRIGGERED EXTRA "
            "SCANS) remains the one that actually runs."
        ),
    )


@dataclass(frozen=True)
class ExperimentReadinessReport:
    ready: bool
    blockers: list[Blocker]
    ground_truth_summary: dict[str, dict[str, int]]  # outcome -> status -> count
    is_pilot: bool = False
    pilot_label: Optional[str] = None


def check_experiment_readiness(
    cohort: Sequence[SweepCase],
    registry: Registry,
    allow_sans_only_pilot: bool = False,
    use_adaptive_replacement: bool = False,
) -> ExperimentReadinessReport:
    """Run once per evaluation, before any CSV/JSON/PNG is written.

    `allow_sans_only_pilot`: opt-in only, defaults False (Part 6 - "do not
    activate it prematurely"). When True AND every SANS-specific check clears
    while venous does not, the report is marked ready with `is_pilot=True` and an
    explicit `pilot_label` - venous's blockers are still returned (not dropped),
    tagged so a caller can show "venous excluded from this pilot", never silently
    presented as the full two-outcome study. Today this can never actually
    activate (SANS progression/monitoring-rule are also unapproved) - this is
    infrastructure for once they are, not a current escape hatch.

    `use_adaptive_replacement`: opt-in only, defaults False. When True, adds
    Part 5's authorization check to the blocker list if unapproved - as a
    GLOBAL/policy-scope blocker (see `global_blockers` below), never an
    outcome-scope one, and therefore never eligible for pilot-mode exclusion.

    Round-3 correction ("fix pilot-mode authorization bypass"): blockers are
    tracked in three separate scopes - `sans_blockers` and `venous_blockers`
    (outcome-scope, exactly as before) and `global_blockers` (experiment/
    policy-scope - today, only the adaptive-replacement authorization check).
    SANS-only pilot mode may exclude ONLY venous outcome blockers; it must
    NEVER bypass a global blocker, since a global blocker's scope is the whole
    experiment, not one outcome. Before this correction, an unapproved
    use_adaptive_replacement request could be silently dropped from a pilot
    report because the pilot condition only inspected sans_blockers/
    venous_blockers, never the combined list the global blocker had already
    been appended to - see tests/test_experiment_readiness.py's
    test_pilot_mode_never_bypasses_an_unapproved_global_blocker.
    """
    sans_blockers: list[Blocker] = []
    venous_blockers: list[Blocker] = []
    global_blockers: list[Blocker] = []
    summary: dict[str, dict[str, int]] = {}

    for outcome in ("sans", "venous"):
        outcome_blockers = sans_blockers if outcome == "sans" else venous_blockers

        # Check 1: ground-truth onset/event consistency (original check).
        cohort_summary = summarize_ground_truth(cohort, outcome)
        summary[outcome] = cohort_summary.counts
        if not cohort_summary.is_fully_resolved:
            outcome_blockers.append(
                Blocker(
                    capability=f"{outcome}_ground_truth_consistency",
                    blocked_by=[],
                    message=(
                        f"{outcome} ground truth is not fully resolved for "
                        f"detection-delay/missed-event/false-escalation scoring "
                        f"(status counts: {cohort_summary.counts}). An event "
                        f"flagged with unknown onset, or no event-occurrence "
                        f"model at all, must never be scored as healthy, "
                        f"detected, or a valid zero."
                    ),
                )
            )

        # Check 2: physiological progression capability - independent of check 1.
        # This is the specific fix for "approving onset timing alone cannot
        # produce an apparently valid full experiment": even a cohort with
        # PERFECT ground-truth consistency still blocks here.
        progression_ready, progression_state = _progression_capability_ready(outcome, registry)
        if not progression_ready:
            outcome_blockers.append(
                Blocker(
                    capability=f"{outcome}_physiological_progression",
                    blocked_by=[],
                    message=(
                        f"{outcome} has no implemented physiological progression "
                        f"model ({progression_state}). The synthetic event FLAG "
                        f"(ground truth) existing is not the same thing as an "
                        f"OBSERVABLE measurement signal existing - no code path "
                        f"superimposes an event signal onto the flat/noisy "
                        f"baseline every astronaut currently receives, so there "
                        f"is nothing for the monitoring engine to detect even "
                        f"when onset timing is fully known."
                    ),
                )
            )

        # Check 3: monitoring-rule authorization - independent of checks 1-2.
        if not _monitoring_rule_ready(outcome):
            outcome_blockers.append(
                Blocker(
                    capability=f"{outcome}_monitoring_rule",
                    blocked_by=[],
                    message=(
                        f"monitoring.engine has no authorized evidence-to-"
                        f"probability/tier rule for {outcome} "
                        f"(MONITORING_PROBABILITY_IMPLEMENTED). Even a perfect "
                        f"measurement would have no way to become a Repeat/"
                        f"Consult/Urgent escalation tied to that evidence."
                    ),
                )
            )

        # Check 4 (venous only): the three conditions Part 4 names, reported
        # individually so a partial fix to just one is visible as such.
        if outcome == "venous":
            status = _venous_specific_status(registry)
            missing = [k for k, v in status.items() if not v]
            if missing:
                outcome_blockers.append(
                    Blocker(
                        capability="venous_eligibility_conditions",
                        blocked_by=[],
                        message=(
                            f"venous evaluation requires ALL THREE of an approved "
                            f"event-occurrence model, an approved onset model, "
                            f"and an implemented measurement-generation chain - "
                            f"current status: {status}. Missing: {missing}."
                        ),
                    )
                )

    # Part 5: adaptive-replacement authorization, only checked if requested.
    # GLOBAL/policy scope, deliberately kept out of sans_blockers/venous_blockers
    # (round-3 correction) - an unapproved, explicitly-requested replacement
    # policy blocks the WHOLE experiment, not "the venous half of it", so it
    # must never be eligible for the pilot exclusion below.
    if use_adaptive_replacement:
        authorized, replacement_blocker = check_adaptive_replacement_authorized(registry)
        if not authorized and replacement_blocker is not None:
            global_blockers.append(replacement_blocker)

    blockers = global_blockers + sans_blockers + venous_blockers

    # Part 6: the opt-in SANS-only pilot. Never changes what was computed above -
    # only changes whether `ready` is allowed to be True while venous still has
    # blockers, and always surfaces that fact explicitly via is_pilot/pilot_label.
    # `not global_blockers` is the round-3 fix: pilot mode may exclude ONLY
    # venous's own outcome-scope blockers - a global blocker (e.g. an
    # unapproved, explicitly-requested adaptive-replacement policy) must always
    # block, pilot or not, since it is not scoped to venous at all.
    if allow_sans_only_pilot and not sans_blockers and not global_blockers and venous_blockers:
        return ExperimentReadinessReport(
            ready=True,
            blockers=venous_blockers,  # kept, not dropped - "excluded", not "resolved"
            ground_truth_summary=summary,
            is_pilot=True,
            pilot_label=SANS_ONLY_PILOT_LABEL,
        )

    return ExperimentReadinessReport(ready=not blockers, blockers=blockers, ground_truth_summary=summary)
