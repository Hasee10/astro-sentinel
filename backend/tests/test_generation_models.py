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


def test_every_spec_blocked_against_real_unapproved_registry(registry):
    """None of the 14 real assumptions are approved - every known capability must
    report something other than READY."""
    for capability, spec in GENERATION_MODEL_SPECS.items():
        result = check_readiness(spec, registry)
        assert result.state != ModelReadiness.READY, capability
        assert result.reasons, capability


def test_numerical_assumption_unapproved_blocks_as_unapproved_assumption(registry):
    spec = GENERATION_MODEL_SPECS["personal_onsd_baseline_values"]
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.BLOCKED_UNAPPROVED_ASSUMPTION


def test_scope_decision_unapproved_blocks_as_unsupported_scientific_use(registry):
    """jugular_scan_values requires venous_probability_model, a SCOPE_DECISION kind
    assumption - that must report UNSUPPORTED_SCIENTIFIC_USE, not the numeric
    BLOCKED_UNAPPROVED_ASSUMPTION state."""
    spec = GENERATION_MODEL_SPECS["jugular_scan_values"]
    result = check_readiness(spec, registry)
    assert result.state == ModelReadiness.UNSUPPORTED_SCIENTIFIC_USE


def test_unregistered_capability_blocks_as_missing_model_rule(registry):
    for capability in ("sans_venous_onset_day_assignment", "trigger_firing_simulation_model"):
        spec = GENERATION_MODEL_SPECS[capability]
        result = check_readiness(spec, registry)
        assert result.state == ModelReadiness.BLOCKED_MISSING_MODEL_RULE


def test_approving_the_numerical_assumption_alone_still_blocks_on_missing_rule(registry):
    """Defect 2 regression at the readiness-interface level: approval is not enough
    without has_implemented_rule=True."""
    approved = _approve(registry.assumptions["onsd_baseline_sd_values"], 0.3)
    fixture_registry = Registry(
        parameters=registry.parameters,
        assumptions={**registry.assumptions, "onsd_baseline_sd_values": approved},
    )
    spec = GENERATION_MODEL_SPECS["personal_onsd_baseline_values"]
    result = check_readiness(spec, fixture_registry)
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
