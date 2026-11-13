"""Deliverable 2: the one authoritative monitoring function, assess_history().

What this can legitimately compute, and why:
- Measurement quality (ok/degraded/failed/unknown) IS sourced: onsd_measurement_protocol
  and onsd_technical_artifacts are established acquisition rules, not invented.
- The Urgent-on-red-flag-symptom and Repeat-on-poor-quality tiers ARE sourced: Table 2
  of the mission brief states both rules directly, independent of any probability
  threshold.
- A VENOUS probability (ASTROSENTINEL, 2026-11-04): now computable, because
  venous_probability_model (scope) and jugular_flow_risk_mapping (the LR values) are
  both approved - see _compute_venous_probability below. This is a Rahat-provided
  SIMULATION PLACEHOLDER model, not derived from any cited source (no jugular
  sensitivity/specificity/LR data exists in the parameter sheet) - every probability
  it produces carries probability_label="Simulation placeholder - unvalidated" and
  must never be shown as a validated clinical estimate. Uses ONLY the single latest
  available flow-class observation per assessment - sequential daily likelihood
  ratios are never multiplied together (per the approval's own explicit condition).
- A SANS probability is still NOT computable: sans_prior_mapping's 2026-11-04 approval
  authorizes a synthetic GENERATION-layer susceptibility/event/time-prior scheme (see
  simulation/physiological_generation.py) for ground truth only - it does not supply
  an evidence-updated MONITORING-layer formula, so probability.sans stays None here,
  with an explanation naming what is still missing.

SANS and venous are assessed by two independent nested functions that never share state
or read each other's scan/signal evidence - there is no code path that could produce a
combined score.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.models import AstronautDayObservation, QualityStatus, ScanType, TierReason, TierValue, measurements_of
from monitoring.measurement_quality import derive_onsd_quality
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
    "venous": ["venous_probability_model", "jugular_flow_risk_mapping"],
}
TIER_THRESHOLD_BLOCKERS = ["decision_tier_thresholds"]

# Which outcomes have an actual implemented MONITORING-layer probability formula.
# sans_prior_mapping being active is deliberately NOT enough on its own to put
# "sans" in this set: that approval authorizes simulation/physiological_generation.py's
# generation-layer ground-truth scheme only (see its value_or_range note) - it does
# not supply (and was never asked to supply) an evidence-updated monitoring formula.
# Without this explicit set, `inactive` below would read as empty for sans the
# moment sans_prior_mapping and decision_tier_thresholds are both active, wrongly
# implying a monitoring model exists when none does.
MONITORING_PROBABILITY_IMPLEMENTED = {"venous"}

SIMULATION_PLACEHOLDER_LABEL = "Simulation placeholder - unvalidated"

# Monitor/Unresolved rank below Repeat below Consult below Urgent - used to combine a
# probability-threshold tier with a flow-class minimum-tier floor by taking the more
# severe of the two, never by overwriting one with the other.
_TIER_RANK = {
    TierValue.MONITOR: 0,
    TierValue.UNRESOLVED: 0,
    TierValue.REPEAT: 1,
    TierValue.CONSULT: 2,
    TierValue.URGENT: 3,
}


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    outcome: str
    text: str
    status: str = "suggested"
    ground_review_required: bool = False
    follow_up_day: int | None = None
    follow_up_rule: str
    quality_repeat_required: bool = False


class OutcomeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probability: float | None = None
    probability_label: str | None = None
    tier: TierValue
    tier_reason: TierReason  # section 4: WHY, kept structurally separate from the tier itself
    measurement_quality: QualityStatus | None = None
    evidence_references: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    explanation: str
    recommended_action: RecommendedAction | None = None
    evidence_day: int | None = None


class AssessmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    astronaut_id: str
    run_id: str | None = None
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
    if len({o.metadata.run_id for o in history}) > 1:
        raise HistoryError("history must belong to one simulation run")
    days = [o.day for o in history]
    if len(set(days)) != len(days):
        raise HistoryError(f"history contains duplicate day entries: {days}")
    return sorted(history, key=lambda o: o.day)


def _latest_scan_of(history: list[AstronautDayObservation], scan_types: set[ScanType]):
    for obs in reversed(history):  # history is chronological; walk backward for "latest"
        for scan in measurements_of(obs):
            if scan.type in scan_types:
                return scan
    return None


def _any_red_flag(history: list[AstronautDayObservation], scan_types: set[ScanType]) -> bool:
    """Section 4 note: this is intentionally "sticky" - once ANY day in history
    carries a red-flag symptom, every later assessment stays Urgent forever,
    because there is no human-approved resolution/reset/clearance rule. This
    function does not, and must not, implement one on its own initiative (that
    would be inventing an automatic medical clearance rule)."""
    return any(
        scan.type in scan_types and scan.red_flag_symptom
        for obs in history for scan in measurements_of(obs)
    )


def _compute_venous_probability(
    history: list[AstronautDayObservation], registry: Registry
) -> tuple[float | None, str | None]:
    """Prior-odds x LR using ONLY the single latest available flow-class observation -
    never a running/multiplied posterior across multiple days (per
    venous_probability_model's approval condition). Returns (probability, flow_class)
    or (None, None) if the model isn't fully approved or no usable evidence exists.
    An unreliable reading (quality recorded as anything other than OK) is never used
    as evidence, the same discipline applied to ONSD elsewhere in this module."""
    if not (
        registry.assumptions["venous_probability_model"].is_active()
        and registry.assumptions["jugular_flow_risk_mapping"].is_active()
    ):
        return None, None

    # A technical failure is not new physiological evidence. Retain the latest
    # explicitly usable observation; never multiply correlated daily LRs.
    latest = next((scan for o in reversed(history) for scan in measurements_of(o)
                   if scan.type in VENOUS_SCAN_TYPES
                   and scan.quality is not None
                   and scan.quality.status == QualityStatus.OK
                   and scan.jugular_flow_class is not None), None)
    if latest is None or latest.jugular_flow_class is None:
        return None, None
    if latest.quality is not None and latest.quality.status != QualityStatus.OK:
        return None, None

    config = registry.assumptions["jugular_flow_risk_mapping"].value_or_range
    lr_map = config["flow_class_likelihood_ratios"]
    flow_class = latest.jugular_flow_class
    if flow_class not in lr_map:
        return None, None

    prior = config["starting_synthetic_prior_pct"] / 100.0
    prior_odds = prior / (1 - prior)
    posterior_odds = prior_odds * lr_map[flow_class]
    posterior_probability = posterior_odds / (1 + posterior_odds)
    return posterior_probability, flow_class


def _tier_from_probability_pct(probability_pct: float, registry: Registry) -> TierValue:
    config = registry.assumptions["decision_tier_thresholds"].value_or_range
    if probability_pct >= config["urgent_min_pct"]:
        return TierValue.URGENT
    if probability_pct >= config["consult_min_pct"]:
        return TierValue.CONSULT
    if probability_pct >= config["repeat_min_pct"]:
        return TierValue.REPEAT
    return TierValue.MONITOR


def _minimum_tier_for_flow_class(flow_class: str | None, registry: Registry) -> TierValue | None:
    """Part 3's explicit floor: stagnant/retrograde flow are never allowed to read
    below Repeat, regardless of what the probability threshold alone would say -
    implemented as an explicit floor (not left to "the numbers happen to work out"),
    so it stays correct even if decision_tier_thresholds is later swept."""
    if flow_class is None or not registry.assumptions["jugular_flow_risk_mapping"].is_active():
        return None
    config = registry.assumptions["jugular_flow_risk_mapping"].value_or_range
    if flow_class in config.get("tier_flags", {}):
        return TierValue.REPEAT
    return None


def _assess_outcome(
    history: list[AstronautDayObservation],
    outcome: str,
    scan_types: set[ScanType],
    registry: Registry,
) -> OutcomeAssessment:
    latest_scan = _latest_scan_of(history, scan_types)
    # Phase 7: derive quality for an ONSD scan the caller left unset, using the one
    # sourced on-axis rule (monitoring/measurement_quality.py) - never overrides a
    # quality the caller already recorded.
    if latest_scan is not None and latest_scan.type == ScanType.ONSD and latest_scan.quality is None:
        quality = derive_onsd_quality(latest_scan).status
    else:
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
            tier_reason=TierReason.RED_FLAG_SYMPTOM,
            measurement_quality=quality,
            evidence_references=evidence_references,
            limitations=[f"No approved probability model ({inactive}); escalation is rule-based only."],
            explanation=(
                "A red-flag symptom was recorded. Per the mission brief's decision tiers "
                "(Table 2), this escalates to Urgent independent of any probability "
                "calculation, which is not performed here. NOTE: this rule is 'sticky' - "
                "any red flag anywhere in history keeps every later day's assessment "
                "Urgent too (see _any_red_flag), since no human-approved "
                "resolution/reset/clearance policy currently exists. This is a deliberate "
                "conservative default, not an oversight - see "
                "handoff/research_lead/DECISIONS_NEEDED_NOW.md."
            ),
        )

    if quality in (QualityStatus.DEGRADED, QualityStatus.FAILED, QualityStatus.UNKNOWN):
        if len(history) > 1:
            previous = _assess_outcome(history[:-1], outcome, scan_types, registry)
            if _TIER_RANK[previous.tier] >= _TIER_RANK[TierValue.CONSULT]:
                return previous.model_copy(update={
                    "tier_reason": TierReason.PERSISTENT_SERIOUS_EVIDENCE,
                    "measurement_quality": quality,
                    "limitations": previous.limitations + [
                        "Latest scan is technically unreliable. Prior serious evidence is retained; no clearance rule is approved."
                    ],
                    "explanation": previous.explanation + " Latest acquisition needs repeating; it does not clear the existing alert.",
                })
        return OutcomeAssessment(
            probability=None,
            tier=TierValue.REPEAT,
            tier_reason=TierReason.MEASUREMENT_QUALITY,
            measurement_quality=quality,
            evidence_references=evidence_references,
            limitations=[f"No approved probability model applies to this reading ({inactive})."]
            if inactive
            else ["The latest relevant reading's quality is unreliable; it is not used as probability evidence."],
            explanation=(
                f"The latest relevant scan quality is '{quality.value}'. Per the mission "
                "brief, a failed, poor, or quality-indeterminate scan should barely move "
                "the estimate and is flagged for repeat. IMPORTANT: this Repeat is a "
                "MEASUREMENT-QUALITY finding only - it is not, and must never be "
                "interpreted as, evidence that a physiological event was detected. No "
                "other Repeat-triggering rule (e.g. a genuine measurement trend) is "
                "implemented or approved today."
            ),
        )

    probability: float | None = None
    flow_class_used: str | None = None
    if outcome == "venous":
        probability, flow_class_used = _compute_venous_probability(history, registry)

    if probability is not None:
        tier = _tier_from_probability_pct(probability * 100.0, registry)
        floor = _minimum_tier_for_flow_class(flow_class_used, registry)
        if floor is not None and _TIER_RANK[floor] > _TIER_RANK[tier]:
            tier = floor
        return OutcomeAssessment(
            probability=probability,
            probability_label=SIMULATION_PLACEHOLDER_LABEL,
            tier=tier,
            tier_reason=TierReason.PROBABILITY_THRESHOLD,
            measurement_quality=quality,
            evidence_references=evidence_references + ["jugular_flow_risk_mapping", "decision_tier_thresholds"],
            limitations=[
                "HYPOTHETICAL/SYNTHETIC: computed from a simulation-placeholder Bayesian "
                "model (prior-odds x likelihood-ratio for the single latest flow-class "
                "observation), not derived from any cited source and not a validated "
                "clinical estimate. Sequential daily likelihood ratios are never "
                "multiplied together."
            ],
            explanation=(
                f"Venous probability computed as prior-odds x LR using the latest "
                f"observed flow class ('{flow_class_used}'), per the approved "
                f"jugular_flow_risk_mapping values, thresholded per "
                f"decision_tier_thresholds. Labeled '{SIMULATION_PLACEHOLDER_LABEL}' - "
                "this is a hackathon demonstration model, not a clinically validated "
                "risk estimate, and must never be presented as one."
            ),
        )

    if outcome not in MONITORING_PROBABILITY_IMPLEMENTED:
        scope_note = (
            "sans_prior_mapping is approved, but only for the generation-layer "
            "synthetic ground-truth scheme in simulation/physiological_generation.py "
            "- not a monitoring-layer formula."
            if not inactive
            else f"Also unapproved: {inactive}."
        )
        limitation = f"No monitoring-layer {outcome} probability formula is implemented here. {scope_note}"
        explanation = (
            f"No numeric {outcome} probability can be computed: no evidence-updated "
            f"monitoring formula exists for it in this module, independent of which "
            f"assumptions are approved for other purposes. Returning an explicit "
            f"unresolved state rather than a fabricated estimate."
        )
    elif inactive:
        limitation = f"No active (approved) assumption authorizes a {outcome} probability calculation: {inactive}."
        explanation = (
            f"No numeric {outcome} probability can be computed: the parameter sheet "
            f"does not currently provide a validated prior/likelihood-ratio mapping or "
            f"decision-tier threshold for it, and none of {inactive} is approved. "
            "Returning an explicit unresolved state rather than a fabricated estimate."
        )
    else:
        limitation = (
            f"A {outcome} probability model is approved, but no usable evidence "
            "(a valid, good-quality flow-class observation) is available in this "
            "astronaut's history yet."
        )
        explanation = (
            f"No numeric {outcome} probability can be computed yet: the approved model "
            "needs a valid flow-class observation of acceptable quality, and none is "
            "present in this astronaut's history. Returning an explicit unresolved "
            "state rather than a fabricated estimate."
        )

    return OutcomeAssessment(
        probability=None,
        tier=TierValue.UNRESOLVED,
        tier_reason=TierReason.INSUFFICIENT_EVIDENCE_FOR_PROBABILITY,
        measurement_quality=quality,
        evidence_references=evidence_references,
        limitations=[limitation],
        explanation=explanation,
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

    from monitoring.actions import describe_action
    for name, assessment, types in (("sans", sans, SANS_SCAN_TYPES), ("venous", venous, VENOUS_SCAN_TYPES)):
        evidence = [o for o in sorted_history for scan in measurements_of(o) if scan.type in types
                    and scan.quality is not None and scan.quality.status == QualityStatus.OK]
        assessment.evidence_day = evidence[-1].day if evidence else None
        assessment.recommended_action = RecommendedAction(**describe_action(assessment, name))

    return AssessmentResult(
        astronaut_id=sorted_history[-1].astronaut_id,
        run_id=sorted_history[-1].metadata.run_id,
        as_of_day=as_of_day,
        sans=sans,
        venous=venous,
    )
