"""Phase 6 (Unified Prompt 6-7, section 3): the explicit scientific generation-model
interface.

For every physiological-generation capability this project might someday implement,
declaring its dependencies here is a READINESS CHECK, never permission to invent a
value for them (section 3.2). A capability may only report READY when ALL of the
following are simultaneously true:

1. Every `required_parameters` id exists in the Scientific Parameter Registry.
2. Every `required_assumptions` id is `is_active()` (approved, with an assigned
   value/decision) in the Experimental Assumption Registry.
3. `has_implemented_rule` is True - i.e. a tested generation algorithm actually
   exists in `simulation/generator.py` for this capability (Defect 2 of the prior
   corrective review: an approved number is not a working algorithm).

`check_readiness()` is the ONLY function in this codebase allowed to compute one of
the five `ModelReadiness` states below, and it never writes to the registry or to
`has_implemented_rule` - those are facts supplied by the human research lead and by
whoever implements the algorithm, respectively.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from registry.design_decisions import DESIGN_DECISIONS
from registry.loader import Registry
from registry.models import AssumptionKind


class ModelReadiness(str, Enum):
    """Engineering states (section 3.6) - never medical diagnoses."""

    READY = "ready"
    BLOCKED_MISSING_PARAMETER = "blocked_missing_parameter"
    BLOCKED_UNAPPROVED_ASSUMPTION = "blocked_unapproved_assumption"
    BLOCKED_MISSING_MODEL_RULE = "blocked_missing_model_rule"
    UNSUPPORTED_SCIENTIFIC_USE = "unsupported_scientific_use"


@dataclass(frozen=True)
class ReadinessResult:
    state: ModelReadiness
    reasons: list[str]


@dataclass(frozen=True)
class GenerationModelSpec:
    """Approval-ready technical spec for one blocked generation capability
    (section 3.7) - everything a research lead needs to approve it, and everything
    an implementer needs to build and test it, in one place.
    """

    capability: str
    required_input_fields: tuple[str, ...]
    required_parameters: tuple[str, ...]
    # Assumption ids this capability needs active. An id with NO entry in the
    # registry at all (section 3's "unregistered" gaps) always forces
    # BLOCKED_MISSING_MODEL_RULE, since there is no number OR scope decision to
    # approve yet - only a design rule to propose and sign off on.
    required_assumptions: tuple[str, ...]
    has_implemented_rule: bool
    output_fields: tuple[str, ...]
    output_units: str
    scientific_context: str
    expected_verification_tests: tuple[str, ...]
    research_lead_decision_required: str
    # Issue D (Unified Prompt 8-9): for a capability with no Experimental
    # Assumption slot at all, a DesignDecision id (registry/design_decisions.py)
    # that must be approved before this capability can ever be READY - lets the
    # block clear naturally once BOTH the decision is approved AND
    # has_implemented_rule is True, instead of staying hardcoded forever.
    design_decision_id: Optional[str] = None


def check_readiness(spec: GenerationModelSpec, registry: Registry) -> ReadinessResult:
    missing_params = [p for p in spec.required_parameters if p not in registry.parameters]
    if missing_params:
        return ReadinessResult(
            ModelReadiness.BLOCKED_MISSING_PARAMETER,
            [f"missing scientific parameter: {p!r}" for p in missing_params],
        )

    # Split unapproved assumptions by kind: a SCOPE_DECISION gap means the *use* of
    # the underlying data is itself not yet sanctioned (UNSUPPORTED_SCIENTIFIC_USE) -
    # distinct from a NUMERICAL gap, where the use is fine in principle but no value
    # has been assigned yet (BLOCKED_UNAPPROVED_ASSUMPTION). An id absent from the
    # registry entirely has no number or decision to approve - just a missing rule.
    scope_blockers: list[str] = []
    numeric_blockers: list[str] = []
    unregistered: list[str] = []
    for aid in spec.required_assumptions:
        assumption = registry.assumptions.get(aid)
        if assumption is None:
            unregistered.append(aid)
            continue
        if not assumption.is_active():
            if assumption.assumption_kind == AssumptionKind.SCOPE_DECISION:
                scope_blockers.append(aid)
            else:
                numeric_blockers.append(aid)

    if scope_blockers:
        return ReadinessResult(
            ModelReadiness.UNSUPPORTED_SCIENTIFIC_USE,
            [f"scope decision not approved: {a!r}" for a in scope_blockers],
        )
    if numeric_blockers:
        return ReadinessResult(
            ModelReadiness.BLOCKED_UNAPPROVED_ASSUMPTION,
            [f"blocked: assumption(s) not approved: {numeric_blockers}"],
        )
    if spec.design_decision_id is not None:
        decision = DESIGN_DECISIONS.get(spec.design_decision_id)
        if decision is None or not decision.is_approved():
            return ReadinessResult(
                ModelReadiness.BLOCKED_MISSING_MODEL_RULE,
                [f"design decision not approved: {spec.design_decision_id!r}"],
            )

    if unregistered or not spec.has_implemented_rule:
        reasons = [f"no registry entry exists for: {a!r}" for a in unregistered]
        if not spec.has_implemented_rule:
            reasons.append(
                "no generation algorithm is implemented in simulation/generator.py yet - "
                "approval alone does not produce numbers"
            )
        return ReadinessResult(ModelReadiness.BLOCKED_MISSING_MODEL_RULE, reasons)

    return ReadinessResult(ModelReadiness.READY, [])


# ---------------------------------------------------------------------------
# The eight currently-known generation-model capabilities (six registered
# physiological-generation gaps + two unregistered simulation-design gaps).
# IMPLEMENTED_GENERATION_ALGORITHMS lists which capabilities have a tested
# algorithm today - empty, because none does yet (Defect 2).
#
# Adding a capability name here (Unified Prompt 10-11 section 6.2) is a claim
# that: (1) its required parameters/assumptions are approved, (2) a concrete,
# documented generation algorithm for it exists in simulation/generator.py -
# not a stub, (3) that algorithm's inputs/outputs/units match this spec's
# declared `required_input_fields`/`output_fields`/`output_units` exactly, and
# (4) dedicated, deterministic, passing tests exist for it. Do not add an entry
# here just because its assumption got approved - check_readiness() already
# distinguishes those two conditions on purpose (see BLOCKED_UNAPPROVED_ASSUMPTION
# vs. BLOCKED_MISSING_MODEL_RULE above), and this set is the only thing standing
# between "approved" and a falsely-reported READY.
# ---------------------------------------------------------------------------

IMPLEMENTED_GENERATION_ALGORITHMS: frozenset[str] = frozenset(
    {
        # ASTROSENTINEL (2026-11-04): simulation/physiological_generation.py now
        # implements these three, tested in tests/test_physiological_generation.py.
        # Each produces only a flat/noisy-around-baseline trajectory (no progression
        # signal for any astronaut, event-flagged or not) - see that module's
        # docstring for exactly why, and what remains blocked.
        "personal_onsd_baseline_values",
        "onsd_scan_values",
        "measurement_quality_failure_injection",
    }
)
# NOTE: the two unregistered-gap capabilities below (sans_venous_onset_day_assignment,
# trigger_firing_simulation_model) do NOT read this frozenset - their
# has_implemented_rule is set directly on each GenerationModelSpec, by design, since
# each also carries its own design_decision_id gate and deserves an explicit, separate,
# by-hand flip rather than one more name added to a shared set. See
# trigger_firing_simulation_model's spec entry below and
# evaluation.sweep.TRIGGER_FIRING_MODEL_IMPLEMENTED, which is flipped alongside it.

GENERATION_MODEL_SPECS: dict[str, GenerationModelSpec] = {
    "personal_onsd_baseline_values": GenerationModelSpec(
        capability="personal_onsd_baseline_values",
        required_input_fields=("astronaut_id", "random_seed"),
        required_parameters=("onsd_baseline_spread_assumption", "onsd_healthy_baseline_range"),
        required_assumptions=("onsd_baseline_sd_values",),
        has_implemented_rule="personal_onsd_baseline_values" in IMPLEMENTED_GENERATION_ALGORITHMS,
        output_fields=("scan.onsd_mm (as a per-astronaut baseline, day 1)",),
        output_units="mm",
        scientific_context=(
            "Per-astronaut synthetic ONSD baseline, sampled around the healthy "
            "range using an approved within-person/between-astronaut SD."
        ),
        expected_verification_tests=(
            "baseline falls within onsd_healthy_baseline_range for every astronaut",
            "baseline spread matches the approved SD within sampling tolerance",
            "reproducible for a fixed seed",
        ),
        research_lead_decision_required=(
            "Approve a numeric SD (or range to sweep) for onsd_baseline_sd_values."
        ),
    ),
    "onsd_scan_values": GenerationModelSpec(
        capability="onsd_scan_values",
        required_input_fields=("astronaut_id", "day", "personal_baseline", "random_seed"),
        required_parameters=("onsd_baseline_spread_assumption", "onsd_healthy_baseline_range"),
        required_assumptions=("onsd_baseline_sd_values",),
        has_implemented_rule="onsd_scan_values" in IMPLEMENTED_GENERATION_ALGORITHMS,
        output_fields=("scan.onsd_mm (day > 1, drift from baseline)",),
        output_units="mm",
        scientific_context=(
            "Daily synthetic ONSD reading drifting from the astronaut's own "
            "baseline. Requires both the baseline (above) and, for a non-healthy "
            "scenario, an approved progression model (see sans_prior_mapping / "
            "decision_tier_thresholds in the monitoring-layer specs, not "
            "generation-layer) - until that exists, only a flat/no-drift synthetic "
            "trajectory would be defensible, and even that still needs the "
            "baseline SD above approved first."
        ),
        expected_verification_tests=(
            "no scenario-correlated drift exists for a HEALTHY astronaut",
            "no SANS/venous cross-correlation is introduced",
            "values stay within the plausible range used for onsd_healthy_baseline_range",
        ),
        research_lead_decision_required=(
            "Same SD approval as personal_onsd_baseline_values, plus (separately, "
            "monitoring-layer) a progression rule before any non-flat trajectory "
            "may be generated for a non-healthy scenario."
        ),
    ),
    "daily_hrv_weak_signal": GenerationModelSpec(
        capability="daily_hrv_weak_signal",
        required_input_fields=("astronaut_id", "day", "random_seed"),
        required_parameters=("hrv_onsd_coefficient", "hrv_confounders"),
        required_assumptions=("hrv_trigger_assumed_accuracy",),
        has_implemented_rule="daily_hrv_weak_signal" in IMPLEMENTED_GENERATION_ALGORITHMS,
        output_fields=("weak_signals.hrv_hf_power", "weak_signals.hrv_lf_hf"),
        output_units="dimensionless ratio",
        scientific_context=(
            "Daily cheap HRV signal, swept across assumed trigger-accuracy values "
            "for the sensitivity analysis. No HRV-to-ONSD coefficient exists in "
            "the source, so even the direction/shape of this signal relative to a "
            "hidden event is undefined without one."
        ),
        expected_verification_tests=(
            "signal distribution does not encode the hidden onset day directly "
            "(no literal leakage of ground truth into the generated value)",
            "sweeping the assumed accuracy changes trigger behavior predictably "
            "in the evaluation layer, not the raw signal's units/shape",
        ),
        research_lead_decision_required=(
            "Approve the swept accuracy value list/range AND (separately, see "
            "trigger_firing_simulation_model below) the method translating an "
            "accuracy value into actual day-by-day signal/trigger behavior."
        ),
    ),
    "daily_ptt_weak_signal": GenerationModelSpec(
        capability="daily_ptt_weak_signal",
        required_input_fields=("astronaut_id", "day", "random_seed"),
        required_parameters=(),
        required_assumptions=("ptt_trigger_assumed_usefulness",),
        has_implemented_rule="daily_ptt_weak_signal" in IMPLEMENTED_GENERATION_ALGORITHMS,
        output_fields=("weak_signals.ptt_ms",),
        output_units="ms",
        scientific_context=(
            "Optional secondary trigger modifier. Not in Table 4 at all - named "
            "only in the mission brief's prose, and explicitly lower priority "
            "than HRV."
        ),
        expected_verification_tests=(
            "confirm scope: should PTT even be generated for this hackathon demo",
        ),
        research_lead_decision_required=(
            "Confirm whether PTT is in scope at all before any further spec work."
        ),
    ),
    "jugular_scan_values": GenerationModelSpec(
        capability="jugular_scan_values",
        required_input_fields=("astronaut_id", "day", "random_seed"),
        required_parameters=(
            "jugular_csa_by_gravity_level",
            "jugular_area_velocity_cutoffs",
            "jugular_ultrasound_measures_inflight",
        ),
        required_assumptions=("jugular_flow_risk_mapping", "venous_probability_model"),
        has_implemented_rule="jugular_scan_values" in IMPLEMENTED_GENERATION_ALGORITHMS,
        output_fields=("scan.jugular_area_mm2", "scan.jugular_flow_class", "scan.jugular_collapsibility_lost"),
        output_units="mm2 (area); categorical (flow class); bool (collapsibility)",
        scientific_context=(
            "Synthetic jugular measurement generation. `venous_probability_model` "
            "is a SCOPE DECISION (not a number) on whether venous monitoring may "
            "ever be numeric at all - this capability is blocked on that decision "
            "in addition to the jugular_flow_risk_mapping number."
        ),
        expected_verification_tests=(
            "generated flow class stays within the qualitative categories the "
            "source document actually describes (antegrade/stagnant/retrograde)",
            "no numeric venous probability is derived from this without "
            "venous_probability_model separately approving that use",
        ),
        research_lead_decision_required=(
            "Confirm venous_probability_model's scope decision (qualitative-only "
            "vs. numeric), then approve jugular_flow_risk_mapping's numeric "
            "mapping if a risk-flag signal is wanted."
        ),
    ),
    "measurement_quality_failure_injection": GenerationModelSpec(
        capability="measurement_quality_failure_injection",
        required_input_fields=("astronaut_id", "day", "scan_type", "random_seed"),
        required_parameters=("onsd_technical_artifacts", "onsd_measurement_protocol"),
        required_assumptions=("onsd_scan_failure_rate",),
        has_implemented_rule="measurement_quality_failure_injection" in IMPLEMENTED_GENERATION_ALGORITHMS,
        output_fields=("scan.quality.status", "scan.quality.reasons"),
        output_units="categorical",
        scientific_context=(
            "Randomly injecting degraded/failed scan quality at a synthetic rate, "
            "to exercise the Repeat-tier pathway realistically. Distinct from "
            "monitoring/measurement_quality.py's deterministic on-axis rule, which "
            "is already implemented and needs no approval (it only derives "
            "quality from a scan's own on_axis field, never injects noise)."
        ),
        expected_verification_tests=(
            "observed failure rate matches the approved rate within sampling tolerance",
            "failure injection is independent of scenario label (no leakage)",
        ),
        research_lead_decision_required="Approve a numeric synthetic scan failure rate.",
    ),
    "sans_venous_onset_day_assignment": GenerationModelSpec(
        capability="sans_venous_onset_day_assignment",
        required_input_fields=("astronaut_id", "scenario_label", "mission_duration_days", "random_seed"),
        required_parameters=(),
        required_assumptions=(),  # no registry slot exists - see docstring
        has_implemented_rule=False,
        design_decision_id="sans_venous_onset_day_assignment",
        output_fields=("ground_truth.sans_onset_day", "ground_truth.venous_onset_day"),
        output_units="mission day (int)",
        scientific_context=(
            "Which day within the 30-day mission a hidden SANS/venous onset is "
            "placed, for a non-healthy scenario. A simulation-engineering choice, "
            "not a sourced parameter - but an unreviewed choice here would "
            "silently shape every downstream detection-delay metric."
        ),
        expected_verification_tests=(
            "chosen rule is deterministic given the seed",
            "onset day distribution is identical across scenario classes that "
            "share the same rule (no accidental difficulty tilt)",
        ),
        research_lead_decision_required=(
            "Propose and approve a convention: e.g. a fixed day, or a day sampled "
            "from a declared range/distribution."
        ),
    ),
    "trigger_firing_simulation_model": GenerationModelSpec(
        capability="trigger_firing_simulation_model",
        required_input_fields=("astronaut_id", "day", "assumed_trigger_accuracy", "hidden_onset_day"),
        required_parameters=(),
        required_assumptions=(),  # no registry slot exists - see docstring
        # ASTROSENTINEL (2026-11-04): evaluation/trigger_model.py implements this,
        # tested in tests/test_trigger_model.py - flipped by hand alongside
        # evaluation.sweep.TRIGGER_FIRING_MODEL_IMPLEMENTED (see that flag's own
        # 5-point comment for exactly what this claims).
        has_implemented_rule=True,
        design_decision_id="trigger_firing_simulation_model",
        output_fields=("whether the adaptive scheduler's trigger fires on a given day",),
        output_units="boolean",
        scientific_context=(
            "Translates an assumed trigger accuracy/usefulness value (e.g. 0.7) "
            "into which specific days a synthetic trigger fires for a given case. "
            "This is the single gap that blocks the crossover experiment "
            "regardless of what else gets approved - see "
            "evaluation/sweep.py::sweep_blockers()."
        ),
        expected_verification_tests=(
            "firing behavior never reads the hidden onset day through any path "
            "other than the explicitly-approved model itself",
            "'accuracy' is not silently conflated with classifier "
            "sensitivity/specificity unless the research lead says so explicitly",
        ),
        research_lead_decision_required=(
            "Choose and approve a method (e.g. a sensitivity/specificity model, "
            "or a fixed lead-time model) - see "
            "handoff/research_lead/BLOCKER_QUESTIONS.md items 8-9."
        ),
    ),
    "sans_physiological_progression": GenerationModelSpec(
        capability="sans_physiological_progression",
        required_input_fields=("astronaut_id", "day", "sans_onset_day", "personal_baseline", "random_seed"),
        required_parameters=(),
        required_assumptions=(),  # no registry slot exists - see design_decisions.py
        # 2026-11-10: simulation/physiological_generation.py's
        # generate_sans_progression_offset() implements this, tested in
        # tests/test_physiological_generation.py - flipped by hand, same
        # convention as trigger_firing_simulation_model above. Implementing and
        # testing the algorithm does NOT activate it: the function itself checks
        # design_decision_id's is_approved() and returns 0.0 unconditionally
        # until Rahat approves it, so this flip changes no live output today -
        # only check_readiness()'s truthful statement of what code exists.
        has_implemented_rule=True,
        design_decision_id="sans_physiological_progression",
        output_fields=("scan.onsd_mm (event-superimposed trajectory, day > onset)",),
        output_units="mm",
        scientific_context=(
            "ASTROSENTINEL correction (2026-11-04), Part 1: distinct from "
            "onsd_scan_values (READY - baseline + flat/noisy drift for EVERY "
            "astronaut, event-flagged or not). This capability is specifically "
            "the shape/rate by which an event-flagged astronaut's trajectory "
            "departs from that flat baseline after onset. Blocking detection "
            "metrics on sans_venous_onset_day_assignment alone (WHEN) is not "
            "sufficient without this (WHAT HAPPENS) - evaluation/"
            "experiment_readiness.py checks both, separately, so approving "
            "onset timing alone can never make an experiment read as fully ready."
        ),
        expected_verification_tests=(
            "a HEALTHY astronaut's trajectory is bit-for-bit identical with and "
            "without this capability enabled (no leakage into non-event cases)",
            "an event-flagged astronaut's post-onset trajectory is statistically "
            "distinguishable from a healthy astronaut's, using only the approved "
            "shape/rate - not an invented one",
            "no SANS/venous cross-correlation is introduced",
        ),
        research_lead_decision_required=(
            "Propose and approve a progression shape (e.g. linear ramp to a "
            "target magnitude over N days) and its parameters - see "
            "handoff/research_lead/DECISIONS_NEEDED_NOW.md item 2."
        ),
    ),
}
