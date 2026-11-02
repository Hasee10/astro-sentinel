"""Issue D (Unified Prompt 8-9) tests: registry/design_decisions.py and its wiring
into simulation/generation_models.py and evaluation/sweep.py."""
from __future__ import annotations

from dataclasses import replace

from registry.design_decisions import DESIGN_DECISIONS, DesignDecision
from registry.loader import load_all
from simulation.generation_models import GENERATION_MODEL_SPECS, ModelReadiness, check_readiness


def test_all_design_decisions_start_unapproved():
    for decision_id, decision in DESIGN_DECISIONS.items():
        assert decision.approved is False, decision_id
        assert decision.is_approved() is False, decision_id


def test_decision_requires_both_text_and_approver():
    bare = DesignDecision(decision_id="x", description="d", approved=True)
    assert bare.is_approved() is False  # no decision_text/approved_by

    half = DesignDecision(decision_id="x", description="d", approved=True, decision_text="chosen: option A")
    assert half.is_approved() is False  # no approved_by

    complete = DesignDecision(
        decision_id="x", description="d", approved=True,
        decision_text="chosen: option A", approved_by="Research Lead",
    )
    assert complete.is_approved() is True


def test_known_decision_ids_match_generation_model_specs():
    """The two unregistered generation-model gaps must each reference a real
    DesignDecision id, not a typo'd/missing one."""
    for capability in ("sans_venous_onset_day_assignment", "trigger_firing_simulation_model"):
        spec = GENERATION_MODEL_SPECS[capability]
        assert spec.design_decision_id in DESIGN_DECISIONS


def test_unapproved_design_decision_blocks_readiness():
    registry = load_all()
    spec = GENERATION_MODEL_SPECS["trigger_firing_simulation_model"]
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE
    assert any("design decision not approved" in r for r in result.reasons)


def test_approving_the_decision_alone_still_blocks_without_an_algorithm(monkeypatch):
    """Mirrors Defect 2/Issue D: a decision sign-off is not an implementation."""
    import simulation.generation_models as gm

    approved_decision = DesignDecision(
        decision_id="trigger_firing_simulation_model",
        description="test",
        approved=True,
        decision_text="Use a fixed lead-time model.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(gm.DESIGN_DECISIONS, "trigger_firing_simulation_model", approved_decision)

    registry = load_all()
    spec = GENERATION_MODEL_SPECS["trigger_firing_simulation_model"]
    assert spec.has_implemented_rule is False
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE
    assert any("no generation algorithm is implemented" in r for r in result.reasons)


def test_sweep_blockers_clears_trigger_entry_only_when_both_approved_and_implemented(monkeypatch):
    import evaluation.sweep as sweep_module

    registry = load_all()
    # Neither condition met (today's real state): blocker present.
    blockers = sweep_module.sweep_blockers(registry)
    assert any(b.capability == "trigger_firing_simulation_model" for b in blockers)

    # Decision approved, but algorithm still not implemented: still blocked.
    monkeypatch.setitem(
        sweep_module.DESIGN_DECISIONS,
        "trigger_firing_simulation_model",
        DesignDecision(
            decision_id="trigger_firing_simulation_model", description="test",
            approved=True, decision_text="Use a fixed lead-time model.", approved_by="Research Lead",
        ),
    )
    blockers = sweep_module.sweep_blockers(registry)
    assert any(b.capability == "trigger_firing_simulation_model" for b in blockers)

    # Both conditions met: the blocker clears with no further code change needed
    # beyond flipping this flag once the real algorithm ships.
    monkeypatch.setattr(sweep_module, "TRIGGER_FIRING_MODEL_IMPLEMENTED", True)
    blockers = sweep_module.sweep_blockers(registry)
    assert not any(b.capability == "trigger_firing_simulation_model" for b in blockers)
