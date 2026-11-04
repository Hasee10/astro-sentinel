"""Preflight experiment-readiness check (ASTROSENTINEL correction, 2026-11-04).

`evaluation.sweep.sweep_blockers()` checks whether the right ASSUMPTIONS/DECISIONS
are approved - necessary, but not sufficient. A ground-truth record can be fully
consistent with every approved assumption (sans_venous_onset_day_assignment was
never claimed approved) while still being unusable for missed-event/detection-delay/
false-escalation accounting: `has_sans_event=True, sans_onset_day=None` is NOT the
same thing as "this astronaut is healthy", but `evaluation/metrics.py`'s functions
previously treated `onset_day=None` as exactly that, which silently turned an
unresolved ground-truth gap into a reported "0 missed events". This module exists
to catch that *before* evaluate_policies.py computes or writes a single row - never
inside the metrics functions themselves, which stay pure and are also used directly
by engineering-fixture tests with their own, deliberately simple ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from contracts.models import Blocker
from evaluation.sweep import HiddenGroundTruth, SweepCase


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


@dataclass(frozen=True)
class CohortGroundTruthSummary:
    outcome: str
    counts: dict[str, int]  # EventGroundTruthStatus.value -> count

    @property
    def is_fully_resolved(self) -> bool:
        """True only if every case is CONFIRMED_NONE or CONFIRMED_WITH_ONSET - i.e.
        detection-delay/missed-event/false-escalation metrics are meaningful for the
        WHOLE cohort, not silently correct for a subset and wrong for the rest."""
        return all(
            self.counts.get(status.value, 0) == 0 for status in _UNRESOLVED_STATUSES
        )


def summarize_ground_truth(cohort: Sequence[SweepCase], outcome: str) -> CohortGroundTruthSummary:
    status_fn = GROUND_TRUTH_STATUS_FN[outcome]
    counts: dict[str, int] = {}
    for case in cohort:
        status = status_fn(case.ground_truth)
        counts[status.value] = counts.get(status.value, 0) + 1
    return CohortGroundTruthSummary(outcome=outcome, counts=counts)


@dataclass(frozen=True)
class ExperimentReadinessReport:
    ready: bool
    blockers: list[Blocker]
    ground_truth_summary: dict[str, dict[str, int]]  # outcome -> status -> count


def check_experiment_readiness(cohort: Sequence[SweepCase]) -> ExperimentReadinessReport:
    """Run once per evaluation, before any CSV/JSON/PNG is written. Does not touch
    the registry (that is sweep_blockers()'s job) - this is purely about whether the
    DATA on hand can support the metrics evaluate_policies.py is about to compute."""
    blockers: list[Blocker] = []
    summary: dict[str, dict[str, int]] = {}

    for outcome in ("sans", "venous"):
        cohort_summary = summarize_ground_truth(cohort, outcome)
        summary[outcome] = cohort_summary.counts
        if not cohort_summary.is_fully_resolved:
            extra = (
                " Venous additionally has no approved event-occurrence model at "
                "all (unlike SANS's approved susceptibility/event-rate scheme) - "
                "every venous case reads as undetermined regardless of onset day."
                if outcome == "venous"
                else ""
            )
            blockers.append(
                Blocker(
                    capability=f"{outcome}_detection_metrics",
                    blocked_by=[],
                    message=(
                        f"{outcome} detection-delay/missed-event/false-escalation "
                        f"metrics are not scientifically valid for this cohort "
                        f"(ground-truth status counts: {cohort_summary.counts}). "
                        f"A case with an event flagged but unknown onset day (or "
                        f"with no event-occurrence model at all) must never be "
                        f"counted as healthy, as detected, or as a valid zero. "
                        f"Requires registry/design_decisions.py::"
                        f"sans_venous_onset_day_assignment to be approved and "
                        f"implemented before this cohort can be scored." + extra
                    ),
                )
            )

    return ExperimentReadinessReport(ready=not blockers, blockers=blockers, ground_truth_summary=summary)
