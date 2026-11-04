"""Phase 0 verification for the Experimental Assumption Registry."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from registry.loader import (
    ASSUMPTIONS_PATH,
    RegistryLoadError,
    load_assumptions,
    load_parameters,
)
from registry.models import ApprovalStatus, AssumptionKind, ExperimentalAssumption

EXPECTED_ASSUMPTION_IDS = {
    "sans_prior_mapping",
    "venous_probability_model",
    "decision_tier_thresholds",
    "onsd_baseline_sd_values",
    "hrv_trigger_assumed_accuracy",
    "ptt_trigger_assumed_usefulness",
    "jugular_flow_risk_mapping",
    "onsd_icu_cutoff_reuse_scope",
    "onsd_interobserver_noise_magnitude",
    "fixed_schedule_interval_choice",
    "sans_cnn_reuse_scope",
    "evidence_atlas_lr_reliance",
    "communication_delay_exact_value",
    "onsd_scan_failure_rate",
}


@pytest.fixture(scope="module")
def known_parameter_ids():
    return frozenset(load_parameters())


@pytest.fixture(scope="module")
def assumptions(known_parameter_ids):
    return load_assumptions(known_parameter_ids=known_parameter_ids)


def test_all_14_assumptions_present(assumptions):
    assert len(assumptions) == 14
    assert set(assumptions) == EXPECTED_ASSUMPTION_IDS


# ASTROSENTINEL (2026-11-04): Rahat approved exactly these 8 of 14, each with a
# recorded value/decision and approver - "Do not approve all 14 assumptions
# automatically" is honored by this remaining-6 set staying untouched.
APPROVED_ASSUMPTION_IDS = {
    "sans_prior_mapping",
    "venous_probability_model",
    "decision_tier_thresholds",
    "onsd_baseline_sd_values",
    "hrv_trigger_assumed_accuracy",
    "jugular_flow_risk_mapping",
    "fixed_schedule_interval_choice",
    "onsd_scan_failure_rate",
}
UNAPPROVED_ASSUMPTION_IDS = {
    "ptt_trigger_assumed_usefulness",
    "onsd_icu_cutoff_reuse_scope",
    "onsd_interobserver_noise_magnitude",
    "sans_cnn_reuse_scope",
    "evidence_atlas_lr_reliance",
    "communication_delay_exact_value",
}


def test_approved_and_unapproved_sets_partition_all_14(assumptions):
    assert set(assumptions) == APPROVED_ASSUMPTION_IDS | UNAPPROVED_ASSUMPTION_IDS
    assert APPROVED_ASSUMPTION_IDS & UNAPPROVED_ASSUMPTION_IDS == set()


def test_approved_assumptions_are_active_with_recorded_approver(assumptions):
    for aid in APPROVED_ASSUMPTION_IDS:
        a = assumptions[aid]
        assert a.approval_status == ApprovalStatus.APPROVED, aid
        assert a.approved_by == "Rahat", aid
        assert a.is_active() is True, aid
        assert a.value_or_range is not None, aid


def test_remaining_assumptions_stay_unapproved(assumptions):
    """Do not approve all 14 assumptions automatically - this is the explicit,
    literal check that the 6 not addressed by Rahat's 2026-11-04 approvals are
    untouched."""
    for aid in UNAPPROVED_ASSUMPTION_IDS:
        a = assumptions[aid]
        assert a.approval_status == ApprovalStatus.UNAPPROVED, aid
        assert a.approved_by is None, aid
        assert a.is_active() is False, aid
        assert a.value_or_range is None, aid


def test_every_assumption_has_required_narrative_fields(assumptions):
    for aid, a in assumptions.items():
        assert a.description.strip(), aid
        assert a.scientific_purpose.strip(), aid
        assert a.limitations.strip(), aid


def test_related_parameters_reference_real_parameters(assumptions, known_parameter_ids):
    for aid, a in assumptions.items():
        for pid in a.related_parameters:
            assert pid in known_parameter_ids, f"{aid} references unknown parameter {pid!r}"


def test_high_priority_blockers_are_represented(assumptions):
    """Spot-check: the two highest-stakes gaps from Part 1 of the corrections
    (no combined/invented venous LR, no fabricated SANS prior) must each have an
    explicit, non-trivial assumption entry."""
    venous_text = " ".join([
        assumptions["venous_probability_model"].description,
        assumptions["venous_probability_model"].limitations,
        str(assumptions["venous_probability_model"].value_or_range),
    ]).lower()
    assert "likelihood-ratio" in venous_text or "likelihood ratio" in venous_text
    assert "unvalidated" in venous_text or "simulation placeholder" in venous_text

    prior_text = " ".join([
        assumptions["sans_prior_mapping"].description,
        assumptions["sans_prior_mapping"].scientific_purpose,
        assumptions["sans_prior_mapping"].limitations,
        str(assumptions["sans_prior_mapping"].value_or_range),
    ]).lower()
    assert "synthetic" in prior_text
    assert "not a real clinical prior" in prior_text or "not clinically validated" in prior_text


# ---- strict validation: unauthorized activation must be rejected ----

VALID_ASSUMPTION = {
    "assumption_id": "fixture_assumption",
    "description": "Test",
    "value_or_range": None,
    "scientific_purpose": "Test",
    "assumption_kind": "numerical",
    "related_parameters": [],
    "approval_status": "unapproved",
    "approved_by": None,
    "limitations": "Test",
}


def test_valid_fixture_parses():
    ExperimentalAssumption.model_validate(VALID_ASSUMPTION)


def test_approved_without_approver_rejected():
    """An assumption cannot be marked APPROVED without naming who approved it -
    this is the structural guard against 'unauthorized activation of assumptions'."""
    bad = dict(VALID_ASSUMPTION, approval_status="approved", approved_by=None, value_or_range=1.0)
    with pytest.raises(ValidationError):
        ExperimentalAssumption.model_validate(bad)


def test_approver_set_without_approval_rejected():
    bad = dict(VALID_ASSUMPTION, approval_status="unapproved", approved_by="Someone")
    with pytest.raises(ValidationError):
        ExperimentalAssumption.model_validate(bad)


def test_properly_approved_numerical_fixture_is_active():
    good = dict(
        VALID_ASSUMPTION,
        approval_status="approved",
        approved_by="Clinical Lead",
        value_or_range=1.0,
    )
    a = ExperimentalAssumption.model_validate(good)
    assert a.is_active() is True


def test_invalid_approval_state_rejected():
    bad = dict(VALID_ASSUMPTION, approval_status="definitely_approved_trust_me")
    with pytest.raises(ValidationError):
        ExperimentalAssumption.model_validate(bad)


# ---- Phase 0.1 Issue 2: approved-but-valueless assumptions can no longer activate ----
# This is the reviewer's exact demonstrated exploit: approval_status=approved,
# approved_by="Someone", value_or_range=null used to make is_active() return True.

def test_numerical_assumption_approved_without_value_rejected():
    bad = dict(
        VALID_ASSUMPTION,
        assumption_kind="numerical",
        approval_status="approved",
        approved_by="Someone",
        value_or_range=None,
    )
    with pytest.raises(ValidationError, match="NUMERICAL"):
        ExperimentalAssumption.model_validate(bad)


def test_numerical_assumption_approved_with_string_only_rejected():
    """A bare decision string is not a usable numeric value for a NUMERICAL assumption."""
    bad = dict(
        VALID_ASSUMPTION,
        assumption_kind="numerical",
        approval_status="approved",
        approved_by="Someone",
        value_or_range="sounds good to me",
    )
    with pytest.raises(ValidationError, match="NUMERICAL"):
        ExperimentalAssumption.model_validate(bad)


def test_scope_decision_assumption_approved_without_decision_text_rejected():
    bad = dict(
        VALID_ASSUMPTION,
        assumption_kind="scope_decision",
        approval_status="approved",
        approved_by="Clinical Lead",
        value_or_range=None,
    )
    with pytest.raises(ValidationError, match="SCOPE_DECISION"):
        ExperimentalAssumption.model_validate(bad)


def test_scope_decision_assumption_approved_with_decision_text_is_active():
    """Non-numeric approvals must have an explicit documented decision, not just a
    sign-off - value_or_range holds the decision text itself for this kind."""
    good = dict(
        VALID_ASSUMPTION,
        assumption_kind="scope_decision",
        approval_status="approved",
        approved_by="Clinical Lead",
        value_or_range="Approved: treat as a soft trend marker only, never a hard cutoff.",
    )
    a = ExperimentalAssumption.model_validate(good)
    assert a.is_active() is True


def test_unapproved_assumption_with_a_value_rejected():
    """An UNAPPROVED assumption may not carry any value at all - staged/proposed values
    belong to PROPOSED, not UNAPPROVED."""
    bad = dict(VALID_ASSUMPTION, approval_status="unapproved", value_or_range=1.0)
    with pytest.raises(ValidationError):
        ExperimentalAssumption.model_validate(bad)


def test_approval_does_not_claim_identity_verification():
    """Approval metadata records sign-off; it must not be documented or implemented as
    an authentication mechanism (no verification of who 'approved_by' actually is)."""
    assert "authenticat" not in (ExperimentalAssumption.is_active.__doc__ or "").lower()
    doc = (ExperimentalAssumption.__doc__ or "").lower()
    assert "does not verify the approver" in doc or "not an authentication" in doc


def test_duplicate_assumption_id_rejected(tmp_path):
    entries = [VALID_ASSUMPTION, VALID_ASSUMPTION]
    dup_file = tmp_path / "dup_assumptions.json"
    dup_file.write_text(json.dumps(entries), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="duplicate assumption_id"):
        load_assumptions(path=dup_file)


def test_unknown_related_parameter_rejected(tmp_path):
    entry = dict(VALID_ASSUMPTION, related_parameters=["no_such_parameter"])
    bad_file = tmp_path / "bad_ref_assumptions.json"
    bad_file.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="not found in the Scientific Parameter Registry"):
        load_assumptions(path=bad_file, known_parameter_ids=frozenset({"some_other_param"}))


def test_raw_json_is_a_list_of_14_objects():
    raw = json.loads(ASSUMPTIONS_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 14
