"""Section 5B (Unified Prompt 8-9), Issue D: explicit, unapproved-by-default
design-decision tracking for simulation-engineering choices that are NOT
scientific parameters or clinical assumptions - and therefore do not belong in
the Experimental Assumption Registry, whose 14-item roster is deliberately
locked (see tests/test_assumption_registry.py's
test_all_14_assumptions_present/test_raw_json_is_a_list_of_14_objects; adding
entries there would break those tests, which the project's own review has
repeatedly said to preserve).

A `DesignDecision` becomes usable only when BOTH of the following are true:

1. `approved` is True, with a recorded `decision_text` and `approved_by` - set
   here only by a human directly editing this file (there is no code path that
   flips this), exactly analogous to how a human edits assumptions.json.
2. Its corresponding algorithm/rule is actually implemented in code, tracked
   separately (e.g. `simulation.generation_models.IMPLEMENTED_GENERATION_ALGORITHMS`,
   `evaluation.sweep.TRIGGER_FIRING_MODEL_IMPLEMENTED`).

This is what lets a currently-hardcoded blocker (e.g.
`evaluation/sweep.py::sweep_blockers()`'s trigger-firing entry) clear naturally
once both conditions are met, instead of requiring a future code change to
"just remove the unconditional append" - see Issue D of the review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DesignDecision:
    decision_id: str
    description: str
    approved: bool = False
    decision_text: Optional[str] = None
    approved_by: Optional[str] = None

    def is_approved(self) -> bool:
        return self.approved and bool(self.decision_text and self.decision_text.strip()) and bool(
            self.approved_by and self.approved_by.strip()
        )


# Every entry below starts unapproved. Do not flip `approved=True` here without
# the research lead's actual sign-off recorded in `decision_text`/`approved_by` -
# this file is reviewed the same way registry/data/assumptions.json is.
DESIGN_DECISIONS: dict[str, DesignDecision] = {
    "sans_venous_onset_day_assignment": DesignDecision(
        decision_id="sans_venous_onset_day_assignment",
        description=(
            "Which day within the 30-day mission a hidden SANS/venous onset is "
            "placed for a non-healthy synthetic scenario."
        ),
    ),
    "trigger_firing_simulation_model": DesignDecision(
        decision_id="trigger_firing_simulation_model",
        description=(
            "Method translating an assumed trigger accuracy/usefulness value "
            "into day-by-day synthetic trigger-fire decisions for a case. "
            "Blocks evaluation/sweep.py::sweep_blockers() unconditionally until "
            "approved AND implemented - see handoff/research_lead/"
            "BLOCKER_QUESTIONS.md items 8-9 for the candidate methods."
        ),
        approved=True,
        decision_text=(
            "Approved (ASTROSENTINEL, 2026-11-04): a windowed sensitivity model. "
            "For a case WITH a hidden onset for the relevant outcome, the trigger "
            "fires independently each day within the 5-day window "
            "[onset_day, onset_day+4] with per-day probability "
            "h = 1 - (1 - s) ** (1/5), where s is the swept assumed trigger "
            "accuracy (hrv_trigger_assumed_accuracy) for that sweep point - chosen "
            "so the cumulative probability of firing at least once across the "
            "5 independent daily draws equals s. Outside that window (including "
            "every day for a case with no onset for that outcome), the trigger "
            "fires independently each day at the approved base false-fire rate "
            "(onsd_baseline... see hrv_trigger_assumed_accuracy's "
            "base_false_fire_probability_per_day, swept per "
            "false_fire_probability_sweep). 'Accuracy' (s) here is explicitly NOT "
            "classifier sensitivity/specificity/overall diagnostic accuracy - it is "
            "a scheduling-detection usefulness parameter local to this trigger "
            "model only, and must never be conflated with the ONSD/SANS-CNN "
            "diagnostic-accuracy figures elsewhere in the registry. The firing "
            "model may read the hidden onset day ONLY inside the generator-side/"
            "evaluation-only trigger-signal construction step - the scheduling "
            "POLICY itself (AdaptiveSchedulePolicy, PolicyDayView-based) must "
            "never receive the onset day, only the resulting boolean flag."
        ),
        approved_by="Rahat",
    ),
    "adaptive_scheduling_policy_semantics": DesignDecision(
        decision_id="adaptive_scheduling_policy_semantics",
        description=(
            "Option A (fixed backstop + triggered extra scans, currently "
            "implemented) vs. Option B (defer/replace fixed scans, potentially "
            "reducing total scans, with explicit max-gap/safety rules) vs. "
            "Option C (a fixed scan budget reallocated to more informative "
            "days). See evaluation/policies.py::AdaptiveSchedulePolicy's "
            "docstring and handoff/research_lead/DECISIONS_NEEDED_NOW.md."
        ),
        approved=False,
        decision_text=(
            "PARTIAL, NOT a completed approval (ASTROSENTINEL, 2026-11-04): Rahat "
            "approved Option B (defer/replace fixed scans) IN PRINCIPLE as the "
            "direction for a future adaptive-replacement experiment, explicitly "
            "confirming Option A's limitation (cannot show scan savings) is why a "
            "replacement/deferment capability is wanted. NOT fully approved: the "
            "maximum permitted gap (days) between scans, and the rescheduling/"
            "safety rule for when deferral is disallowed, are both still "
            "unspecified and must not be invented. `approved` stays False until "
            "both numbers exist - an implemented, tested "
            "AdaptiveReplacementSchedulePolicy exists (evaluation/policies.py) "
            "taking a required `max_gap_days` as an explicit constructor argument "
            "with no default, but it is NOT wired into evaluate_policies.py's real "
            "run and must not be until this decision is fully approved."
        ),
        approved_by=None,
    ),
}
