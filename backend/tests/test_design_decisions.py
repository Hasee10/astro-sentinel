"""Issue D (Unified Prompt 8-9) tests: registry/design_decisions.py and its wiring
into simulation/generation_models.py and evaluation/sweep.py."""
from __future__ import annotations

from dataclasses import replace

from registry.design_decisions import DESIGN_DECISIONS, DesignDecision
from registry.loader import load_all
from simulation.generation_models import GENERATION_MODEL_SPECS, ModelReadiness, check_readiness


def test_design_decisions_match_rahat_2026_11_04_approvals():
    """trigger_firing_simulation_model is now genuinely approved; the other two
    (sans_venous_onset_day_assignment, and adaptive_scheduling_policy_semantics -
    approved only in principle, missing its max-gap parameter) correctly stay not
    fully approved."""
    assert DESIGN_DECISIONS["trigger_firing_simulation_model"].is_approved() is True
    assert DESIGN_DECISIONS["trigger_firing_simulation_model"].approved_by == "Rahat"
    for decision_id in ("sans_venous_onset_day_assignment", "adaptive_scheduling_policy_semantics"):
        assert DESIGN_DECISIONS[decision_id].is_approved() is False, decision_id


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
    """sans_venous_onset_day_assignment's decision is still genuinely unapproved -
    unlike trigger_firing_simulation_model, which Rahat did approve 2026-11-04."""
    registry = load_all()
    spec = GENERATION_MODEL_SPECS["sans_venous_onset_day_assignment"]
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE
    assert any("design decision not approved" in r for r in result.reasons)


def test_approving_the_decision_alone_still_blocks_without_an_algorithm(monkeypatch):
    """Mirrors Defect 2/Issue D: a decision sign-off is not an implementation.
    sans_venous_onset_day_assignment is the live example today - unlike
    trigger_firing_simulation_model (now genuinely approved AND implemented, see
    test_approval_checkpoint.py), no algorithm exists for this one yet."""
    import simulation.generation_models as gm

    approved_decision = DesignDecision(
        decision_id="sans_venous_onset_day_assignment",
        description="test",
        approved=True,
        decision_text="Use a fixed onset day.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(gm.DESIGN_DECISIONS, "sans_venous_onset_day_assignment", approved_decision)

    registry = load_all()
    spec = GENERATION_MODEL_SPECS["sans_venous_onset_day_assignment"]
    assert spec.has_implemented_rule is False
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE
    assert any("no generation algorithm is implemented" in r for r in result.reasons)


def test_sweep_blockers_clears_trigger_entry_only_when_both_approved_and_implemented(monkeypatch):
    """ASTROSENTINEL (2026-11-04): today's real state is actually "both conditions
    met" (Rahat approved the decision, evaluation/trigger_model.py implements it) -
    so this test now explicitly constructs all three states via monkeypatch rather
    than relying on the ambient registry/module state for the first two."""
    import evaluation.sweep as sweep_module

    registry = load_all()
    unapproved_decision = DesignDecision(decision_id="trigger_firing_simulation_model", description="test")

    # Neither condition met: blocker present.
    monkeypatch.setitem(sweep_module.DESIGN_DECISIONS, "trigger_firing_simulation_model", unapproved_decision)
    monkeypatch.setattr(sweep_module, "TRIGGER_FIRING_MODEL_IMPLEMENTED", False)
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
    # beyond flipping this flag once the real algorithm ships - exactly what
    # actually happened for real on 2026-11-04.
    monkeypatch.setattr(sweep_module, "TRIGGER_FIRING_MODEL_IMPLEMENTED", True)
    blockers = sweep_module.sweep_blockers(registry)
    assert not any(b.capability == "trigger_firing_simulation_model" for b in blockers)
