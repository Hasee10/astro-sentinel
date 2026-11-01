"""Phase 0.1 Issue 1 / Issue 5 (points 1-4): the fail-closed parameter usage gate.

These tests prove that correct, well-formed data (unlike Issue 3's malformed-data
tests) still cannot be used predictively without explicit authorization. Clinical use
restrictions are enforced here at the usage-check layer, not just described in prose.
"""
from __future__ import annotations

import pytest

from registry.loader import load_all
from registry.models import AuthorizedOperation, TargetMeasurement
from registry.usage import check_parameter_usage


@pytest.fixture(scope="module")
def registry():
    return load_all()


def test_reference_display_always_permitted_regardless_of_endpoint(registry):
    """Scientific reference display must remain possible even when predictive use is
    prohibited."""
    decision = check_parameter_usage(
        registry,
        "onsd_icu_icp_cutoff",
        AuthorizedOperation.REFERENCE_DISPLAY,
        TargetMeasurement.VENOUS,  # deliberately mismatched endpoint
    )
    assert decision.permitted is True


def test_treatment_decision_always_rejected_unconditionally(registry):
    """No metadata path may ever authorize a treatment-related calculation."""
    for pid in ("onsd_icu_icp_cutoff", "sans_cnn_sensitivity", "communication_delay_one_way"):
        decision = check_parameter_usage(
            registry, pid, AuthorizedOperation.TREATMENT_DECISION, TargetMeasurement.SANS
        )
        assert decision.permitted is False
        assert "treatment" in decision.reason.lower()


# ---- Issue 5.2: ICP performance cannot automatically become SANS progression performance ----

def test_icp_evidence_cannot_automatically_score_sans_probability(registry):
    for pid in (
        "onsd_icu_icp_cutoff",
        "onsd_accuracy_koziarz_2019",
        "onsd_accuracy_ohle_2015",
        "onsd_accuracy_maissan_2015",
        "onsd_pooled_lr_evidence_atlas",
    ):
        decision = check_parameter_usage(
            registry, pid, AuthorizedOperation.PROBABILITY_INPUT, TargetMeasurement.SANS
        )
        assert decision.permitted is False, pid


# ---- Issue 5.3: OCT classifier performance cannot become generic ultrasound reliability ----

def test_oct_classifier_performance_cannot_score_sans_probability(registry):
    for pid in ("sans_cnn_sensitivity", "sans_cnn_specificity", "sans_cnn_accuracy_f1"):
        decision = check_parameter_usage(
            registry, pid, AuthorizedOperation.PROBABILITY_INPUT, TargetMeasurement.SANS
        )
        assert decision.permitted is False, pid


# ---- Issue 5.4: jugular area values cannot automatically become venous-stasis probabilities ----

def test_jugular_geometry_cannot_score_venous_probability(registry):
    for pid in ("jugular_csa_by_gravity_level", "jugular_stasis_prevalence_iss"):
        decision = check_parameter_usage(
            registry, pid, AuthorizedOperation.PROBABILITY_INPUT, TargetMeasurement.VENOUS
        )
        assert decision.permitted is False, pid


# ---- Issue 5.1: cross-endpoint predictive use is rejected ----

def test_cross_endpoint_predictive_use_rejected(registry):
    """A SANS-scoped parameter requested for the VENOUS endpoint must be rejected on
    scope grounds specifically (distinct from the 'no assumption backs it yet' case)."""
    decision = check_parameter_usage(
        registry,
        "onsd_accuracy_koziarz_2019",
        AuthorizedOperation.PROBABILITY_INPUT,
        TargetMeasurement.VENOUS,
    )
    assert decision.permitted is False
    assert "scoped to sans" in decision.reason.lower()


def test_no_parameter_currently_authorizes_probability_input(registry):
    """Do not automatically authorize any probability-related calculation: right now,
    with zero approved assumptions, this must hold for every single parameter."""
    for parameter_id, parameter in registry.parameters.items():
        decision = check_parameter_usage(
            registry, parameter_id, AuthorizedOperation.PROBABILITY_INPUT, parameter.target_measurement
        )
        assert decision.permitted is False, parameter_id


def test_unknown_parameter_id_rejected(registry):
    decision = check_parameter_usage(
        registry, "not_a_real_parameter", AuthorizedOperation.REFERENCE_DISPLAY, TargetMeasurement.SANS
    )
    assert decision.permitted is False
