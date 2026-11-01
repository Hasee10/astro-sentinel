"""Deliverable 2: the one authoritative monitoring function, assess_history().

What this can legitimately compute right now, and why:
- Measurement quality (ok/degraded/failed) IS sourced: onsd_measurement_protocol and
  onsd_technical_artifacts are established acquisition rules, not invented.
- The Urgent-on-red-flag-symptom and Repeat-on-poor-quality tiers ARE sourced: Table 2
  of the mission brief states both rules directly, independent of any probability
  threshold.
- A numeric SANS or venous probability is NOT currently computable: no prior, no
  likelihood ratio, and no decision-tier threshold is an active (approved) assumption.
  Every probability this function returns is therefore None, with an explanation naming
  the exact assumption(s) that would need to be approved to change that.

SANS and venous are assessed by two independent nested functions that never share state
or read each other's scan/signal evidence - there is no code path that could produce a
combined score.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.models import AstronautDayObservation, QualityStatus, ScanType, TierValue
from registry.loader import Registry

# Which scan types are read as evidence for which outcome. A symptom record's
# red-flag flag is routed by this same mapping, since the source document lists
# "symptoms" as one undifferentiated confirmatory-measurement category - this routing
# is an explicit, documented interpretive choice, not a value taken from the sheet.
SANS_SCAN_TYPES = {ScanType.ONSD, ScanType.OCT, ScanType.VISUAL_ACUITY, ScanType.SYMPTOMS}
VENOUS_SCAN_TYPES = {ScanType.JUGULAR}

# capability -> blocking assumption_id(s), mirrors simulation/generator.py's pattern
PROBABILITY_BLOCKERS = {
    "sans": ["sans_prior_mapping"],
    "venous": ["venous_probability_model"],
}
TIER_THRESHOLD_BLOCKERS = ["decision_tier_thresholds"]


class OutcomeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probability: float | None = None
    probability_label: str | None = None
    tier: TierValue
    measurement_quality: QualityStatus | None = None
    evidence_references: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    explanation: str


class AssessmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    astronaut_id: str
    as_of_day: int
    sans: OutcomeAssessment
    venous: OutcomeAssessment


class HistoryError(ValueError):
    pass


def _validate_and_sort(history: list[AstronautDayObservation]) -> list[AstronautDayObservation]:
    if not history:
        raise HistoryError("history must contain at least one observation")
    astronaut_ids = {o.astronaut_id for o in history}
    if len(astronaut_ids) > 1:
        raise HistoryError(f"history must belong to one astronaut, got {astronaut_ids}")
    days = [o.day for o in history]
    if len(set(days)) != len(days):
        raise HistoryError(f"history contains duplicate day entries: {days}")
    return sorted(history, key=lambda o: o.day)


def _latest_scan_of(history: list[AstronautDayObservation], scan_types: set[ScanType]):
    for obs in reversed(history):  # history is chronological; walk backward for "latest"
        if obs.scan is not None and obs.scan.type in scan_types:
            return obs.scan
    return None


def _any_red_flag(history: list[AstronautDayObservation], scan_types: set[ScanType]) -> bool:
    return any(
        obs.scan is not None and obs.scan.type in scan_types and obs.scan.red_flag_symptom
        for obs in history
    )


def _assess_outcome(
    history: list[AstronautDayObservation],
    outcome: str,
    scan_types: set[ScanType],
    registry: Registry,
) -> OutcomeAssessment:
    latest_scan = _latest_scan_of(history, scan_types)
    quality = latest_scan.quality.status if (latest_scan and latest_scan.quality) else None
    evidence_references: list[str] = []
    if latest_scan is not None:
        evidence_references.append(
            "onsd_measurement_protocol" if outcome == "sans" else "jugular_ultrasound_measures_inflight"
        )

    blocking_assumptions = PROBABILITY_BLOCKERS[outcome] + TIER_THRESHOLD_BLOCKERS
    inactive = [aid for aid in blocking_assumptions if not registry.assumptions[aid].is_active()]

    if _any_red_flag(history, scan_types):
        return OutcomeAssessment(
            probability=None,
            tier=TierValue.URGENT,
            measurement_quality=quality,
            evidence_references=evidence_references,
            limitations=[f"No approved probability model ({inactive}); escalation is rule-based only."],
            explanation=(
                "A red-flag symptom was recorded. Per the mission brief's decision tiers "
                "(Table 2), this escalates to Urgent independent of any probability "
                "calculation, which is not performed here."
            ),
        )

    if quality in (QualityStatus.DEGRADED, QualityStatus.FAILED):
        return OutcomeAssessment(
            probability=None,
            tier=TierValue.REPEAT,
            measurement_quality=quality,
            evidence_references=evidence_references,
            limitations=[f"No approved probability model ({inactive})."],
            explanation=(
                f"The latest relevant scan quality is '{quality.value}'. Per the mission "
                "brief, a failed or poor scan should barely move the estimate and is "
                "flagged for repeat."
            ),
        )

    return OutcomeAssessment(
        probability=None,
        tier=TierValue.UNRESOLVED,
        measurement_quality=quality,
        evidence_references=evidence_references,
        limitations=[
            f"No active (approved) assumption authorizes a {outcome} probability "
            f"calculation: {inactive}."
        ],
        explanation=(
            f"No numeric {outcome} probability can be computed: the parameter sheet "
            f"does not currently provide a validated prior/likelihood-ratio mapping or "
            f"decision-tier threshold for it, and none of {inactive} is approved. "
            "Returning an explicit unresolved state rather than a fabricated estimate."
        ),
    )


def assess_history(history: list[AstronautDayObservation], registry: Registry) -> AssessmentResult:
    """The one authoritative monitoring function - see module docstring.

    `history` must belong to a single astronaut and should contain only observations
    up to (and including) the day being assessed; this function has no other way to
    see "the future" than what is in `history`, so chronological truncation is the
    caller's responsibility (score_crew.py enforces it).
    """
    sorted_history = _validate_and_sort(history)
    as_of_day = sorted_history[-1].day

    sans = _assess_outcome(sorted_history, "sans", SANS_SCAN_TYPES, registry)
    venous = _assess_outcome(sorted_history, "venous", VENOUS_SCAN_TYPES, registry)

    return AssessmentResult(
        astronaut_id=sorted_history[-1].astronaut_id,
        as_of_day=as_of_day,
        sans=sans,
        venous=venous,
    )
