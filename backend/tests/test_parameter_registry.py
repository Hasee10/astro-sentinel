"""Phase 0 verification for the Scientific Parameter Registry.

Checks actual transcribed content against Mission_NASA_updated.docx Table 4,
not just that files exist and parse.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from registry.loader import (
    PARAMETERS_PATH,
    RegistryLoadError,
    load_parameters,
)
from registry.models import ScientificParameter, TargetMeasurement

EXPECTED_PARAMETER_IDS = {
    "sans_cnn_sensitivity",
    "sans_cnn_specificity",
    "sans_cnn_accuracy_f1",
    "jugular_stasis_prevalence_iss",
    "jugular_csa_by_gravity_level",
    "optic_disc_edema_tilt_study",
    "perioptic_pressure_drop_model",
    "communication_delay_one_way",
    "onsd_icu_icp_cutoff",
    "onsd_healthy_baseline_range",
    "onsd_accuracy_koziarz_2019",
    "onsd_accuracy_ohle_2015",
    "onsd_accuracy_maissan_2015",
    "onsd_pooled_lr_evidence_atlas",
    "onsd_screening_cutoff_busti_2023",
    "onsd_measurement_protocol",
    "onsd_technical_artifacts",
    "onsd_confounders",
    "onsd_interobserver_variability",
    "sans_time_course",
    "jugular_area_velocity_cutoffs",
    "jugular_ultrasound_measures_inflight",
    "hrv_onsd_coefficient",
    "hrv_confounders",
    "onsd_baseline_spread_assumption",
    "personal_baseline_protocol",
}


@pytest.fixture(scope="module")
def params() -> dict[str, ScientificParameter]:
    return load_parameters()


def test_all_26_parameters_present(params):
    assert len(params) == 26
    assert set(params) == EXPECTED_PARAMETER_IDS


# ---- numeric / structured values transcribed accurately ----

def test_sans_cnn_values(params):
    assert params["sans_cnn_sensitivity"].value == 82.8
    assert params["sans_cnn_sensitivity"].unit == "%"
    assert params["sans_cnn_specificity"].value == 85.6
    assert params["sans_cnn_accuracy_f1"].value == {
        "accuracy_pct": 84.2,
        "f1_pct": 84.1,
        "held_out_scans": 945,
    }


def test_jugular_prevalence_and_geometry(params):
    assert params["jugular_stasis_prevalence_iss"].value == {
        "stagnant_or_retrograde": 6,
        "cohort_n": 11,
    }
    assert params["jugular_csa_by_gravity_level"].value == {
        "seated_1g_mm2": 12,
        "g_0_75_mm2": 24,
        "g_0_5_mm2": 34,
        "g_0_25_mm2": 68,
        "supine_1g_mm2": 108,
    }


def test_optic_disc_edema_and_model_output(params):
    assert params["optic_disc_edema_tilt_study"].value == {"cases": 5, "cohort_n": 11}
    assert params["perioptic_pressure_drop_model"].value == {
        "low_mmHg": 1.89,
        "high_mmHg": 3.69,
    }


def test_communication_delay(params):
    for pid in ("communication_delay_one_way",):
        assert params[pid].value == {"low_min": 0, "high_min": 20}
        assert params[pid].unit == "min"


def test_onsd_cutoffs_and_ranges(params):
    cutoff = params["onsd_icu_icp_cutoff"].value
    assert cutoff["cutoff_mm"] == 5.0
    assert cutoff["literature_range_mm"] == [4.8, 5.9]
    assert cutoff["measurement_depth_mm_behind_retina"] == 3
    assert params["onsd_healthy_baseline_range"].value == [4.8, 5.9]
    assert params["onsd_healthy_baseline_range"].unit == "mm"


def test_onsd_accuracy_studies_all_three_distinct(params):
    koziarz = params["onsd_accuracy_koziarz_2019"].value
    ohle = params["onsd_accuracy_ohle_2015"].value
    maissan = params["onsd_accuracy_maissan_2015"].value

    assert koziarz == {
        "cutoff_mm": 5.0,
        "sensitivity_pct": 94,
        "specificity_pct": 87,
        "lr_positive": 7.2,
        "lr_negative": 0.07,
    }
    assert ohle == {
        "sensitivity_pct": 96,
        "specificity_pct": 93,
        "lr_positive": 13.7,
        "lr_negative": 0.04,
    }
    assert maissan == {
        "sensitivity_pct": 94,
        "specificity_pct": 98,
        "lr_positive": 47,
        "lr_negative": 0.06,
    }
    # The three studies must stay distinct - this is the evidentiary disagreement
    # Correction 2 relies on (no single "the" validated SANS LR exists).
    lr_plus_values = {koziarz["lr_positive"], ohle["lr_positive"], maissan["lr_positive"]}
    assert len(lr_plus_values) == 3


def test_onsd_pooled_and_screening_studies(params):
    assert params["onsd_pooled_lr_evidence_atlas"].value == {
        "lr_positive": 12.4,
        "lr_negative": 0.05,
        "studies_pooled": 12,
        "n": 478,
    }
    busti = params["onsd_screening_cutoff_busti_2023"].value
    assert busti["cutoff_mm"] == 5.5
    assert busti["sensitivity_pct"] == 100
    assert busti["specificity_pct"] == 19
    assert busti["n"] == 99


def test_sans_time_course_fd30_risk_rule(params):
    tc = params["sans_time_course"].value
    assert tc["fd7_to_fd10_trt_um"] == 11.9
    assert tc["fd30_choroid_um"] == 24
    assert tc["fd30_risk_rule"] == {
        "delta_trt_below_20um_pct_late_ode": 2,
        "delta_trt_above_29um_pct_edema_55um_or_more": 58,
    }
    assert tc["susceptible_flier_max"] == {"trt_um_at_fd90": 135, "mrw_um_at_fd270": 149}
    assert "course beyond 1 year" in tc["excluded_from_simulation"]
    assert "Moon or Mars gravity effect" in tc["excluded_from_simulation"]


# ---- missing parameters explicitly represented as unresolved (never fabricated) ----

def test_unsourced_numbers_are_null_not_fabricated(params):
    assert params["onsd_interobserver_variability"].value is None
    assert params["hrv_onsd_coefficient"].value is None
    assert params["onsd_baseline_spread_assumption"].value is None
    assert params["jugular_area_velocity_cutoffs"].value["numeric_cutoffs"] is None


def test_unsourced_numbers_have_explanatory_limitations(params):
    for pid in (
        "onsd_interobserver_variability",
        "hrv_onsd_coefficient",
        "onsd_baseline_spread_assumption",
        "jugular_area_velocity_cutoffs",
    ):
        assert params[pid].limitations.strip() != ""
        assert params[pid].verification_status.value in {"not_sourced", "unspecified"}


# ---- evidence classification retained exactly ----

EXPECTED_EVIDENCE = {
    "sans_cnn_sensitivity": "established",
    "sans_cnn_specificity": "established",
    "sans_cnn_accuracy_f1": "established",
    "jugular_stasis_prevalence_iss": "established",
    "jugular_csa_by_gravity_level": "established",
    "optic_disc_edema_tilt_study": "established",
    "perioptic_pressure_drop_model": "model",
    "communication_delay_one_way": "design",
    "onsd_icu_icp_cutoff": "established",
    "onsd_healthy_baseline_range": "established",
    "onsd_accuracy_koziarz_2019": "established",
    "onsd_accuracy_ohle_2015": "established",
    "onsd_accuracy_maissan_2015": "established",
    "onsd_pooled_lr_evidence_atlas": "established",
    "onsd_screening_cutoff_busti_2023": "established",
    "onsd_measurement_protocol": "established",
    "onsd_technical_artifacts": "established",
    "onsd_confounders": "established",
    "onsd_interobserver_variability": "established",
    "sans_time_course": "established",
    "jugular_area_velocity_cutoffs": "hypothesis",
    "jugular_ultrasound_measures_inflight": "established",
    "hrv_onsd_coefficient": "hypothesis",
    "hrv_confounders": "established",
    "onsd_baseline_spread_assumption": "assumption",
    "personal_baseline_protocol": "design",
}


def test_evidence_classifications_match_expected(params):
    """jugular_area_velocity_cutoffs is HYPOTHESIS, not ESTABLISHED: the document's own
    label for that row is 'Qualitative only; animal model', which is not an established
    human clinical finding (Phase 0.1 correction)."""
    actual = {pid: p.evidence_classification.value for pid, p in params.items()}
    assert actual == EXPECTED_EVIDENCE


def test_established_does_not_imply_verified(params):
    """The document flags nearly every 'Established' row as still needing primary-source
    verification. The registry must not silently upgrade evidence_classification into a
    claim of independent verification."""
    established = [p for p in params.values() if p.evidence_classification.value == "established"]
    assert established, "expected at least one established parameter"
    already_verified = [p for p in established if p.verification_status.value == "verified"]
    assert already_verified == [], (
        "no parameter should be marked 'verified' yet - Phase 0 only transcribes the "
        "sheet, it does not independently check primary sources"
    )


# ---- source metadata present for every entry ----

def test_source_metadata_present_for_every_entry(params):
    for pid, p in params.items():
        assert p.source_name.strip(), pid
        assert p.source_document == "Mission_NASA_updated.docx", pid
        assert "Table 4" in p.source_location, pid
        assert p.original_study_context.strip(), pid
        assert p.original_study_endpoint.strip(), pid
        assert p.permitted_use.strip(), pid
        assert p.limitations.strip(), pid


# ---- Phase 0.1 Issue 4: previously-omitted source numbers now present ----

def test_sans_time_course_includes_fluid_shift_context(params):
    """The ~1.5-2.0 L headward fluid-shift figure lives in the SANS time course row's
    own Value cell in the source document but was missing from the structured value -
    confirmed and fixed per independent review."""
    tc = params["sans_time_course"].value
    assert tc["headward_fluid_shift_liters_range"] == [1.5, 2.0]


def test_onsd_icu_cutoff_includes_icp_threshold_and_direction(params):
    cutoff = params["onsd_icu_icp_cutoff"].value
    assert cutoff["icp_threshold_mmhg"] == 20
    assert cutoff["abnormal_direction"] == "above"


def test_jugular_mouse_model_tilt_angle_recorded(params):
    assert params["jugular_area_velocity_cutoffs"].value["mouse_time_course"]["tilt_angle_degrees"] == -30


def test_onsd_measurement_protocol_is_structured(params):
    protocol = params["onsd_measurement_protocol"].value
    assert protocol["calipers_depth_mm"] == 3
    assert protocol["sweeps_averaged"] == 3


def test_personal_baseline_protocol_counts_structured(params):
    protocol = params["personal_baseline_protocol"].value
    assert protocol["sweeps_averaged"] == 3
    assert protocol["baseline_day_count"] == 3


def test_hrv_confounders_includes_onsd_shared_confounders(params):
    """The document's HRV-confounders row names altitude/posture/suctioning as moving
    BOTH HRV and ONSD - a distinct, non-redundant point (shared-confounder risk) that
    was dropped in the first transcription pass."""
    confounders = params["hrv_confounders"].value
    assert "high altitude" in confounders
    assert "prone posture" in confounders
    assert "airway suctioning" in confounders


def test_onsd_accuracy_studies_flag_computed_likelihood_ratios(params):
    """Koziarz/Ohle/Maissan report sensitivity/specificity directly; the document
    states LR+/LR- are 'Computed' from those, not directly reported by the studies."""
    for pid in ("onsd_accuracy_koziarz_2019", "onsd_accuracy_ohle_2015", "onsd_accuracy_maissan_2015"):
        assert "computed" in params[pid].limitations.lower(), pid


def test_original_study_endpoint_distinguishes_borrowed_evidence(params):
    """Issue 1's four named examples: each must have an original_study_endpoint that is
    visibly different from (not just equal to) the SANS/venous application domain."""
    checks = {
        "onsd_icu_icp_cutoff": "intracranial pressure",
        "sans_cnn_sensitivity": "image classification",
        "jugular_csa_by_gravity_level": "gravity",
        "hrv_onsd_coefficient": "mouse",
        "jugular_area_velocity_cutoffs": "mouse",
    }
    for pid, must_contain in checks.items():
        endpoint = params[pid].original_study_endpoint.lower()
        assert must_contain in endpoint, f"{pid}: {endpoint!r}"


# ---- target_measurement scoping: SANS vs venous never silently mixed ----

def test_no_venous_parameter_carries_accuracy_statistics(params):
    """Correction 2 / scientific safety: there is no sensitivity, specificity, or
    likelihood-ratio data for venous stasis anywhere in the source. Prove the registry
    does not smuggle any in under a venous-scoped parameter."""
    venous_params = [p for p in params.values() if p.target_measurement == TargetMeasurement.VENOUS]
    assert venous_params, "expected at least one venous-scoped parameter"
    for p in venous_params:
        if isinstance(p.value, dict):
            keys = {k.lower() for k in p.value.keys()}
            assert not keys & {"sensitivity_pct", "specificity_pct", "lr_positive", "lr_negative"}, (
                f"{p.parameter_id} unexpectedly carries diagnostic-accuracy fields"
            )


def test_cross_context_parameters_carry_explicit_caveats(params):
    """Parameters established in one clinical context (ICU/ICP, an OCT classifier) but
    scoped here to SANS must say, in permitted_use, that they are not yet validated for
    SANS progression - this is the guard against 'Parameters intended for one clinical
    endpoint cannot silently be used for another.'"""
    must_caveat_not_validated = [
        "onsd_icu_icp_cutoff",
        "onsd_accuracy_koziarz_2019",
        "onsd_accuracy_ohle_2015",
        "onsd_accuracy_maissan_2015",
    ]
    caveat_markers = ("assumption", "unresolved", " not ")
    for pid in must_caveat_not_validated:
        text = params[pid].permitted_use
        text_lower = f" {text.lower()} "
        assert "sans" in text_lower, f"{pid} permitted_use does not mention SANS: {text!r}"
        assert any(marker in text_lower for marker in caveat_markers), (
            f"{pid} permitted_use missing an explicit not-yet-validated caveat: {text!r}"
        )

    for pid in ("sans_cnn_sensitivity", "sans_cnn_specificity", "sans_cnn_accuracy_f1"):
        text = params[pid].permitted_use
        assert "image-classifier" in text or "OCT image" in text, pid
        assert "not" in text.lower(), pid


def test_target_measurement_values_are_valid_enum_members(params):
    allowed = {"sans", "venous", "not_clinical"}
    for p in params.values():
        assert p.target_measurement.value in allowed


# ---- loading reliability ----

def test_registry_loads_reliably_and_deterministically():
    first = load_parameters()
    second = load_parameters()
    assert set(first) == set(second)
    assert {k: v.model_dump() for k, v in first.items()} == {
        k: v.model_dump() for k, v in second.items()
    }


def test_raw_json_is_a_list_of_26_objects():
    raw = json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 26


# ---- strict validation: deliberately broken fixtures must be rejected ----

VALID_ENTRY = {
    "parameter_id": "fixture_param",
    "name": "Fixture parameter",
    "value": 1.0,
    "unit": "mm",
    "source_name": "Test",
    "source_document": "Mission_NASA_updated.docx",
    "source_location": "Table 4 (Parameter sheet), row \"Fixture\"",
    "original_study_context": "Test context",
    "original_study_endpoint": "Test original endpoint",
    "target_measurement": "sans",
    "evidence_classification": "established",
    "verification_status": "open_paper",
    "permitted_use": "Test use",
    "authorized_operations": [],
    "limitations": "Test limitation",
}


def test_valid_fixture_parses():
    ScientificParameter.model_validate(VALID_ENTRY)


def test_missing_scientific_provenance_rejected():
    bad = dict(VALID_ENTRY, source_name="")
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_numeric_value_without_unit_rejected():
    bad = dict(VALID_ENTRY, unit=None)
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_percentage_out_of_range_rejected():
    bad = dict(VALID_ENTRY, value=150.0, unit="%")
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_negative_mm_measurement_rejected():
    bad = dict(VALID_ENTRY, value=-1.0, unit="mm")
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_invalid_evidence_classification_rejected():
    bad = dict(VALID_ENTRY, evidence_classification="definitely_true")
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_missing_verification_status_rejected():
    bad = dict(VALID_ENTRY)
    del bad["verification_status"]
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_unexpected_extra_field_rejected():
    bad = dict(VALID_ENTRY, extra_field_nobody_asked_for="oops")
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_duplicate_parameter_id_rejected(tmp_path):
    entries = [VALID_ENTRY, VALID_ENTRY]
    dup_file = tmp_path / "dup_parameters.json"
    dup_file.write_text(json.dumps(entries), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="duplicate parameter_id"):
        load_parameters(path=dup_file)


def test_treatment_decision_may_never_be_authorized_by_data():
    bad = dict(VALID_ENTRY, authorized_operations=["treatment_decision"])
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


# ---- Phase 0.1 Issue 3: nested numeric validation ----
# This is the reviewer's exact demonstrated exploit: relabel a parameter as venous and
# give it a bogus nested sensitivity_pct, and the old model validation let it through.

def test_nested_invalid_percentage_rejected():
    bad = dict(
        VALID_ENTRY,
        target_measurement="venous",
        value={"sensitivity_pct": 1000},
    )
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_nested_negative_likelihood_ratio_rejected():
    bad = dict(VALID_ENTRY, value={"lr_positive": -5})
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_nested_large_likelihood_ratio_accepted():
    """Do not apply percentage constraints to likelihood ratios - LR+ of 47 is real
    (onsd_accuracy_maissan_2015) and must not be rejected as 'out of range'."""
    good = dict(VALID_ENTRY, value={"lr_positive": 47})
    ScientificParameter.model_validate(good)


def test_nested_negative_physical_measurement_rejected():
    bad = dict(VALID_ENTRY, value={"onsd_mm": -0.3})
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_nested_negative_delta_measurement_accepted():
    """A legitimate negative change must not be rejected just because the same unit,
    as an absolute measurement, cannot be negative."""
    good = dict(VALID_ENTRY, value={"delta_onsd_mm": -0.3})
    ScientificParameter.model_validate(good)


def test_nested_unordered_range_rejected():
    bad = dict(VALID_ENTRY, value={"example_range_mm": [5.9, 4.8]})
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_nested_unordered_low_high_pair_rejected():
    bad = dict(VALID_ENTRY, value={"low_mm": 10, "high_mm": 2})
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_nested_event_count_exceeding_sample_rejected():
    bad = dict(VALID_ENTRY, value={"cases": 20, "cohort_n": 11})
    with pytest.raises(ValidationError):
        ScientificParameter.model_validate(bad)


def test_nested_event_count_within_sample_accepted():
    good = dict(VALID_ENTRY, value={"cases": 5, "cohort_n": 11})
    ScientificParameter.model_validate(good)


def test_all_real_parameters_pass_nested_validation(params):
    """The full loaded registry already passing (see the `params` fixture) is itself
    the strongest proof here - this just makes the intent explicit."""
    assert len(params) == 26
