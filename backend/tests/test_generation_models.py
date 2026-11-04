"""Phase 6 tests: simulation/generation_models.py's explicit readiness interface."""
from __future__ import annotations

from dataclasses import replace

import pytest

from registry.loader import Registry, load_all
from registry.models import ApprovalStatus
from simulation.generation_models import (
    GENERATION_MODEL_SPECS,
    ModelReadiness,
    check_readiness,
)


@pytest.fixture(scope="module")
def registry():
    return load_all()


def _approve(assumption, value):
    return assumption.model_copy(
        update={"approval_status": ApprovalStatus.APPROVED, "approved_by": "test-fixture", "value_or_range": value}
    )


def test_spec_readiness_against_real_registry_has_no_false_positives(registry):
    """ASTROSENTINEL (2026-11-04): 4/8 capabilities ARE now genuinely READY - the
    invariant this guards is narrower than "nothing is ready": a capability may
    report READY only when it actually has both approvals and an implemented
    algorithm. See tests/test_approval_checkpoint.py for the full expected-state
    table; this test just double-checks every blocked one still carries a reason."""
    for capability, spec in GENERATION_MODEL_SPECS.items():
        result = check_readiness(spec, registry)
        if result.state != ModelReadiness.READY:
            assert result.reasons, capability


def test_numerical_assumption_unapproved_blocks_as_unapproved_assumption(registry):
    """ptt_trigger_assumed_usefulness is one of the 6 Rahat did not approve -
    daily_ptt_weak_signal must still report the numeric-gap state."""
    spec = GENERATION_MODEL_SPECS["daily_ptt_weak_signal"]
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_UNAPPROVED_ASSUMPTION


def test_scope_decision_unapproved_blocks_as_unsupported_scientific_use(registry):
    """jugular_scan_values's real required scope decision (venous_probability_model)
    IS now approved - exercise the UNSUPPORTED_SCIENTIFIC_USE branch itself with a
    fixture registry where it is forced back to unapproved, since no capability in
    the real registry is currently blocked this specific way any more."""
    unapproved_scope = registry.assumptions["venous_probability_model"].model_copy(
        update={"approval_status": ApprovalStatus.UNAPPROVED, "approved_by": None, "value_or_range": None}
    )
    fixture_registry = Registry(
        parameters=registry.parameters,
        assumptions={**registry.assumptions, "venous_probability_model": unapproved_scope},
    )
    spec = GENERATION_MODEL_SPECS["jugular_scan_values"]
    result = check_readiness(spec, fixture_registry)
    assert result.state == ModelReadiness.UNSUPPORTED_SCIENTIFIC_USE


def test_unregistered_capability_with_unapproved_decision_blocks_as_missing_model_rule(registry):
    """sans_venous_onset_day_assignment's design decision remains unapproved - this
    is the still-live example. trigger_firing_simulation_model is now the OTHER
    case (decision approved + algorithm implemented -> READY), covered separately
    in test_approval_checkpoint.py, not here."""
    spec = GENERATION_MODEL_SPECS["sans_venous_onset_day_assignment"]
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE


def test_approving_the_numerical_assumption_alone_still_blocks_on_missing_rule(registry):
    """Defect 2 regression at the readiness-interface level: approval is not enough
    without has_implemented_rule=True. jugular_scan_values is the live, real-registry
    example today: both its required assumptions ARE approved, but no algorithm for
    it exists in simulation/generator.py - unlike personal_onsd_baseline_values,
    which now has both and genuinely reports READY (see test_approval_checkpoint.py)."""
    spec = GENERATION_MODEL_SPECS["jugular_scan_values"]
    for aid in spec.required_assumptions:
        assert registry.assumptions[aid].is_active(), f"expected {aid} to be approved in the real registry"
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE
    assert any("no generation algorithm is implemented" in r for r in result.reasons)


def test_hypothetically_fully_ready_spec_reports_ready(registry):
    """A spec with no dependencies at all and has_implemented_rule=True must report
    READY - proving check_readiness can reach the positive state, not just refuse."""
    trivial_spec = replace(
        GENERATION_MODEL_SPECS["daily_ptt_weak_signal"],
        required_parameters=(),
        required_assumptions=(),
        has_implemented_rule=True,
    )
    result = check_readiness(trivial_spec, registry)
    assert result.state == ModelReadiness.READY
    assert result.reasons == []


def test_missing_parameter_blocks_before_anything_else(registry):
    bogus_spec = replace(
        GENERATION_MODEL_SPECS["daily_ptt_weak_signal"],
        required_parameters=("this_parameter_does_not_exist",),
        required_assumptions=(),
        has_implemented_rule=True,
    )
    result = check_readiness(bogus_spec, registry)
    assert result.state == ModelReadiness.BLOCKED_MISSING_PARAMETER


def test_every_spec_declares_a_research_lead_decision():
    for capability, spec in GENERATION_MODEL_SPECS.items():
        assert spec.research_lead_decision_required.strip(), capability
        assert spec.scientific_context.strip(), capability
        assert spec.expected_verification_tests, capability
