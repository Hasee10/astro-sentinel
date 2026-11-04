"""Unified Prompt 10-11 section 6.1: the strict approval checkpoint. Originally
asserted, against the real registry, that no component could falsely report
READY/approved while everything was unapproved. ASTROSENTINEL (2026-11-04)
legitimately approved 8/14 assumptions + the trigger-firing design decision, so
this file's job is now the SAME acceptance criterion applied to a mixed state:
every capability that IS backed by real approvals + a real algorithm must report
READY, and every capability that is NOT must still correctly report itself
blocked - neither a false positive nor a false negative. Acceptance criterion #5
("Scientific readiness cannot falsely report an unimplemented model as READY")
is still exactly what every assertion below checks.
"""
from __future__ import annotations

from evaluation.sweep import TRIGGER_FIRING_MODEL_IMPLEMENTED, sweep_blockers
from registry.design_decisions import DESIGN_DECISIONS
from registry.loader import load_all
from simulation.generation_models import (
    GENERATION_MODEL_SPECS,
    IMPLEMENTED_GENERATION_ALGORITHMS,
    ModelReadiness,
    check_readiness,
)

# capability -> expected state, now that 8/14 assumptions + the trigger-firing
# decision are approved and 4 algorithms are implemented (see
# simulation/physiological_generation.py, evaluation/trigger_model.py).
EXPECTED_READINESS = {
    "personal_onsd_baseline_values": ModelReadiness.READY,
    "onsd_scan_values": ModelReadiness.READY,
    "measurement_quality_failure_injection": ModelReadiness.READY,
    "trigger_firing_simulation_model": ModelReadiness.READY,
    "daily_hrv_weak_signal": ModelReadiness.BLOCKED_MISSING_MODEL_RULE,
    "daily_ptt_weak_signal": ModelReadiness.BLOCKED_UNAPPROVED_ASSUMPTION,
    "jugular_scan_values": ModelReadiness.BLOCKED_MISSING_MODEL_RULE,
    "sans_venous_onset_day_assignment": ModelReadiness.BLOCKED_MISSING_MODEL_RULE,
}


def test_a_through_f_generation_capabilities_match_expected_readiness():
    """No capability may report READY unless both its approvals AND a tested
    algorithm genuinely exist - and conversely, one that genuinely has both must
    not be falsely reported as still blocked."""
    registry = load_all()
    assert set(EXPECTED_READINESS) == set(GENERATION_MODEL_SPECS)
    for capability, expected_state in EXPECTED_READINESS.items():
        result = check_readiness(GENERATION_MODEL_SPECS[capability], registry)
        assert result.state == expected_state, f"{capability}: {result.state} (reasons: {result.reasons})"

    # E: SANS stays null regardless of approval - sans_prior_mapping authorizes
    # generation-layer ground truth only, never a monitoring-layer probability.
    # F: venous and the tier thresholds ARE now active (the venous model is real).
    registry_active = lambda aid: registry.assumptions[aid].is_active()
    assert registry_active("sans_prior_mapping") is True  # approved, but see monitoring/engine.py
    assert registry_active("venous_probability_model") is True
    assert registry_active("decision_tier_thresholds") is True


def test_g_fixed_scanning_interval_approved():
    registry = load_all()
    assert registry.assumptions["fixed_schedule_interval_choice"].is_active() is True


def test_h_adaptive_scheduling_policy_semantics_still_undecided():
    """Option B approved only IN PRINCIPLE (max-gap/safety rule still missing) -
    must NOT read as a completed approval."""
    decision = DESIGN_DECISIONS["adaptive_scheduling_policy_semantics"]
    assert decision.is_approved() is False
    assert decision.decision_text is not None and "PARTIAL" in decision.decision_text


def test_i_hrv_trigger_generation_approved():
    registry = load_all()
    assert registry.assumptions["hrv_trigger_assumed_accuracy"].is_active() is True


def test_j_trigger_accuracy_sweep_definition_approved_and_implemented():
    """Both the trigger-firing design decision AND its algorithm must be present
    together - the real unblock condition, not either one alone."""
    decision = DESIGN_DECISIONS["trigger_firing_simulation_model"]
    assert decision.is_approved() is True
    assert TRIGGER_FIRING_MODEL_IMPLEMENTED is True


def test_no_generation_algorithm_has_been_marked_implemented_without_justification():
    """Guards against exactly the shortcut section 6.2/6.3 forbid: adding a name
    to the implemented set without the matching approval existing."""
    registry = load_all()
    for capability in IMPLEMENTED_GENERATION_ALGORITHMS:
        spec = GENERATION_MODEL_SPECS[capability]
        for aid in spec.required_assumptions:
            assert registry.assumptions[aid].is_active(), (
                f"{capability} is marked implemented but its required assumption "
                f"{aid!r} is not approved"
            )


def test_real_sweep_blockers_now_empty_the_gate_is_genuinely_open():
    """End-to-end confirmation that the crossover experiment can really run -
    not just that the individual flags are True in isolation. This is the
    single most consequential assertion in this file: if it's wrong, either a
    blocked capability silently became usable, or the gate falsely stayed shut
    on genuinely-approved, genuinely-implemented work."""
    registry = load_all()
    assert sweep_blockers(registry) == []


def test_option_b_adaptive_replacement_stays_unreachable_from_the_real_cli():
    """Independent of sweep_blockers(), the still-unapproved Option B policy
    must not be importable from evaluate_policies.py's module namespace - it may
    exist in evaluation/policies.py (tested there directly) but must never be
    wired into the real pipeline while unapproved."""
    import evaluate_policies

    assert not hasattr(evaluate_policies, "AdaptiveReplacementSchedulePolicy")
