"""Operator-facing workflow instructions, separate from probability and quality.

No retry interval, clinical treatment, or automatic medical clearance is invented.
Due days stay null until the research lead approves scheduling rules.
"""


def describe_action(assessment, outcome: str) -> dict:
    tier = assessment.tier.value
    poor = assessment.measurement_quality is not None and assessment.measurement_quality.value in {
        "failed", "degraded", "unknown"
    }
    if tier == "urgent":
        code, text = "urgent_escalation", "Alert the simulated crew medical officer and request urgent ground review."
    elif tier == "consult":
        code, text = "ground_review", "Request simulated ground-medical review with the recorded evidence."
    elif poor:
        code, text = "technical_reacquisition", (
            "Repeat ultrasound acquisition. This reading cannot reliably update the estimate; "
            "this is a technical measurement issue, not a confirmed physiological event."
        )
    elif tier == "repeat":
        code, text = "confirmatory_measurement", "Request another confirmatory measurement for the recorded physiological evidence."
    elif tier == "monitor":
        code, text = "routine_monitoring", "Continue routine monitoring under the active policy."
    else:
        code, text = "evidence_unavailable", "Review the missing evidence or model approval; an unavailable estimate does not mean zero risk."
    if poor and tier in {"consult", "urgent"}:
        text += " Also repeat the technically inadequate scan; the existing serious alert remains active."
    return {
        "code": code, "outcome": outcome, "text": text,
        "status": "suggested", "ground_review_required": tier in {"consult", "urgent"},
        "follow_up_day": None,
        "follow_up_rule": "Routine policy schedule" if tier == "monitor" else "Exact follow-up timing awaits research-lead approval",
        "quality_repeat_required": poor,
    }
