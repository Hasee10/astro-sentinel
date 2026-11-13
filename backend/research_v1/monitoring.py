"""Observable-only monitoring for gated engineering verification.

Latest-evidence decayed log odds is an explicit pending interpretation, not an
authorization to sequentially compound correlated measurements.
"""
import math

from contracts.models import measurements_of, QualityStatus, TierReason, TierValue
from monitoring.actions import describe_action
from monitoring.engine import AssessmentResult, OutcomeAssessment, RecommendedAction
from research_v1.authorization import SPEC

RANK = {"unresolved": 0, "monitor": 0, "repeat": 1, "consult": 2, "urgent": 3}


def assess(history, starting_prior_pct, *, half_life=7, previous=None):
    if not history or len({o.astronaut_id for o in history}) != 1:
        raise ValueError("One nonempty observable astronaut history required")
    days = [o.day for o in history]
    if days != sorted(set(days)):
        raise ValueError("History must be unique and chronological")
    day = days[-1]
    outcomes = {}
    for outcome, scan_type in (("sans", "onsd"), ("venous", "jugular")):
        entries = [(o.day, scan) for o in history for scan in measurements_of(o) if scan.type.value == scan_type]
        latest = entries[-1][1] if entries else None
        usable = [(d, scan) for d, scan in entries if scan.quality and scan.quality.status in {QualityStatus.OK, QualityStatus.DEGRADED}
                  and (scan.onsd_mm is not None and scan.onsd_baseline_mm is not None if outcome == "sans" else scan.jugular_flow_class in SPEC["venous"]["lr"])]
        evidence_day, evidence = usable[-1] if usable else (None, None)
        probability = None
        explanation = "No usable observation. Missing evidence is not zero risk."
        tier, reason = "unresolved", TierReason.INSUFFICIENT_EVIDENCE_FOR_PROBABILITY
        if evidence is not None:
            if outcome == "sans":
                config = SPEC["sans"]
                prior_pct = min(config["prior_cap_pct"], starting_prior_pct + config["increment_pct_points_per_day"] * (day - 1))
                delta = evidence.onsd_mm - evidence.onsd_baseline_mm
                positive = delta >= config["positive_delta_mm"]
                lr = config["lr_positive"] if positive else config["lr_negative"]
                observation_text = f"ONSD {evidence.onsd_mm:.3f} mm, personal baseline {evidence.onsd_baseline_mm:.3f} mm, delta {delta:+.3f} mm; positive evidence at delta >=0.3 mm"
            else:
                prior_pct = SPEC["venous"]["monitoring_prior_pct"]
                lr = SPEC["venous"]["lr"][evidence.jugular_flow_class]
                observation_text = f"Jugular flow {evidence.jugular_flow_class}; area is not a probability input"
            weight = SPEC["sans"]["poor_log_weight"] if evidence.quality.status == QualityStatus.DEGRADED else 1
            decay = 2 ** (-(day - evidence_day) / half_life)
            prior = prior_pct / 100
            log_odds = math.log(prior / (1 - prior)) + weight * decay * math.log(lr)
            probability = 1 / (1 + math.exp(-log_odds))
            thresholds = SPEC["monitoring"]["threshold_pct"]
            tier = "urgent" if probability * 100 >= thresholds[2] else "consult" if probability * 100 >= thresholds[1] else "repeat" if probability * 100 >= thresholds[0] else "monitor"
            reason = TierReason.PROBABILITY_THRESHOLD
            if outcome == "venous":
                area_flag = (evidence.jugular_area_mm2 is not None and evidence.jugular_baseline_mm2 is not None
                             and evidence.jugular_area_mm2 > SPEC["venous"]["area_flag_multiplier"] * evidence.jugular_baseline_mm2)
                if (area_flag or evidence.jugular_flow_class in {"stagnant", "retrograde"}) and RANK[tier] < 1:
                    tier = "repeat"
                if area_flag:
                    observation_text += "; area >1.2x personal baseline: Tier-2 monitoring flag only"
            explanation = (f"{observation_text}. Evidence day {evidence_day}; LR {lr}; log-evidence weight {weight}; "
                           f"decay {decay:.3f}. Synthetic prior {prior_pct:.2f}%, hypothetical posterior {probability * 100:.2f}%; "
                           f"15/40/80% synthetic thresholds yield {tier}. Latest observation only; no sequential LR multiplication.")
        poor = latest is not None and latest.quality is not None and latest.quality.status in {QualityStatus.DEGRADED, QualityStatus.FAILED, QualityStatus.UNKNOWN}
        prior_assessment = getattr(previous, outcome) if previous else None
        red_flag = any(scan.red_flag_symptom for _, scan in entries)
        if red_flag or (prior_assessment and prior_assessment.tier == TierValue.URGENT):
            tier = "urgent"
            reason = TierReason.RED_FLAG_SYMPTOM if red_flag else prior_assessment.tier_reason
            explanation += " Urgent remains active; no automatic clearance is approved."
        elif poor:
            if prior_assessment and RANK[prior_assessment.tier.value] >= 2 and RANK[tier] < RANK[prior_assessment.tier.value]:
                tier, reason = prior_assessment.tier.value, TierReason.PERSISTENT_SERIOUS_EVIDENCE
                explanation += f" Prior {tier} alert from evidence day {prior_assessment.evidence_day} persists: technically inadequate evidence cannot authorize clearance, even if today's weighted estimate is lower."
            elif RANK[tier] < 2:
                tier, reason = "repeat", TierReason.MEASUREMENT_QUALITY
            explanation += " Technical reacquisition is required independently of physiological concern."
        result = OutcomeAssessment(probability=probability, probability_label=SPEC["label"] if probability is not None else None,
            tier=TierValue(tier), tier_reason=reason, measurement_quality=latest.quality.status if latest and latest.quality else None,
            evidence_day=evidence_day, explanation=explanation,
            evidence_references=["research_v1/spec.json"], limitations=[SPEC["label"], *SPEC["unresolved_interpretations"][:1]])
        action = describe_action(result, outcome)
        follow_up = 1 if tier == "urgent" else 2 if tier in {"repeat", "consult"} else None
        action.update(follow_up_day=day + follow_up if follow_up else None,
                      follow_up_rule=f"Engineering protocol: within {follow_up} day(s)" if follow_up else "Active routine policy")
        result.recommended_action = RecommendedAction(**action)
        outcomes[outcome] = result
    return AssessmentResult(astronaut_id=history[-1].astronaut_id, run_id=history[-1].metadata.run_id, as_of_day=day, **outcomes)
