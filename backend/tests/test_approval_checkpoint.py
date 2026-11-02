"""Unified Prompt 10-11 section 6.1: the strict approval checkpoint. Asserts,
against the REAL (unapproved) registry and design-decision records, that none of
the ten listed experiment components can report itself ready - i.e. that no
component falsely reports READY/approved today. This is the project's own
explicit acceptance-criterion #5 ("Scientific readiness cannot falsely report an
unimplemented model as READY") made directly checkable in one place.
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


def test_a_through_f_generation_and_monitoring_capabilities_all_blocked():
    """A. Synthetic baseline generation, B. Physiological progression,
    C. Measurement noise/failure, D. Event onset assignment, E/F. Monitoring
    probabilities/tier boundaries all route through generation_models.py or
    monitoring/engine.py's hardcoded blockers - none may report READY."""
    registry = load_all()
    for capability, spec in GENERATION_MODEL_SPECS.items():
        result = check_readiness(spec, registry)
        assert result.state != ModelReadiness.READY, f"{capability} falsely reports READY"

    # E/F: monitoring probability/tier-threshold assumptions remain unapproved.
    for assumption_id in ("sans_prior_mapping", "venous_probability_model", "decision_tier_thresholds"):
        assert registry.assumptions[assumption_id].is_active() is False, assumption_id


def test_g_fixed_scanning_interval_unapproved():
    registry = load_all()
    assert registry.assumptions["fixed_schedule_interval_choice"].is_active() is False


def test_h_adaptive_scheduling_policy_semantics_undecided():
    decision = DESIGN_DECISIONS["adaptive_scheduling_policy_semantics"]
    assert decision.is_approved() is False


def test_i_hrv_trigger_generation_unapproved():
    registry = load_all()
    assert registry.assumptions["hrv_trigger_assumed_accuracy"].is_active() is False


def test_j_trigger_accuracy_sweep_definition_unapproved_and_unimplemented():
    """The trigger-firing design decision AND its algorithm must both be
    missing - either one alone being present would not be enough."""
    decision = DESIGN_DECISIONS["trigger_firing_simulation_model"]
    assert decision.is_approved() is False
    assert TRIGGER_FIRING_MODEL_IMPLEMENTED is False


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


def test_real_sweep_blockers_still_fully_blocks_the_experiment():
    """End-to-end confirmation that the strict checkpoint above actually
    prevents the real evaluator from running - not just that the individual
    flags are False in isolation."""
    registry = load_all()
    blockers = sweep_blockers(registry)
    assert len(blockers) >= 4  # 3 required assumptions + trigger-firing model
