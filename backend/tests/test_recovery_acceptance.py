"""Functional/scientific boundaries for the user-relayed gated implementation.

These verify engineering behavior. They do not approve the modeled physiology.
"""
from dataclasses import fields, replace
import json

import pytest

from contracts.models import (AstronautDayObservation, ObservationMetadata, ScanSession,
    ScanMeasurement, MeasurementQuality, QualityStatus, ScanType, measurements_of)
from research_v1.authorization import authorize, SPEC
from research_v1.physiology import make_case, latent, acquire
from research_v1.monitoring import assess
from research_v1.scheduling import DayView, decide
from research_v1.run import run_case, summarize_case, study


def observation(day, onsd=6.0, flow="antegrade", quality=QualityStatus.OK):
    return AstronautDayObservation(astronaut_id="FIXTURE", day=day,
        metadata=ObservationMetadata(run_id="engineering-fixture", synthetic_label=SPEC["label"]),
        scan_session=ScanSession(session_id=f"fixture:{day}", policy="engineering",
            reason_codes=["explicit_test_input"], measurements=[
                ScanMeasurement(type=ScanType.ONSD, onsd_mm=onsd, onsd_baseline_mm=5.35,
                    quality=MeasurementQuality(status=quality)),
                ScanMeasurement(type=ScanType.JUGULAR, jugular_area_mm2=34, jugular_baseline_mm2=34,
                    jugular_flow_class=flow, quality=MeasurementQuality(status=quality))]))


def test_user_relay_never_authorizes_production_execution(tmp_path):
    with pytest.raises(PermissionError, match="independent written"):
        study(tmp_path)
    assert not list(tmp_path.iterdir())
    assert "ENGINEERING FIXTURE" in authorize(engineering_fixture=True)


@pytest.mark.parametrize("scenario", ["healthy", "sans", "venous", "both"])
def test_causal_latent_progression_for_each_outcome(scenario):
    case = make_case("FIXTURE", 42, scenario)
    early, late = latent(case, 1), latent(case, 25)
    assert late[0] - early[0] == pytest.approx(0.6 if scenario in {"sans", "both"} else 0)
    assert (late[1] > early[1]) == (scenario in {"venous", "both"})
    if scenario in {"venous", "both"}:
        assert latent(case, 7)[2] == "antegrade"
        assert latent(case, 8)[2] == "stagnant"
    assert latent(case, 8)[0] == case.onsd_baseline
    assert late[1] <= 108


def test_sans_ramp_is_capped_and_noise_does_not_depend_on_policy():
    case = make_case("FIXTURE", 2, "sans")
    assert latent(case, 13)[0] - case.onsd_baseline == pytest.approx(0.3)
    assert latent(case, 30)[0] - case.onsd_baseline == pytest.approx(0.6)
    assert acquire(case, 8) == acquire(case, 8)


def test_occurrence_random_streams_are_independent():
    cohort = [make_case(f"A{i}", 42) for i in range(1200)]
    for has_sans in (True, False):
        subset = [c for c in cohort if (c.sans_onset is not None) == has_sans]
        assert 0.23 < sum(c.venous_onset is not None for c in subset) / len(subset) < 0.37


def test_probability_quality_and_action_are_separate():
    good = assess([observation(1)], 10)
    assert good.sans.probability == pytest.approx((0.1 / 0.9 * 7.2) / (1 + 0.1 / 0.9 * 7.2))
    assert good.sans.tier.value == "consult"
    assert good.sans.recommended_action.ground_review_required
    poor = assess([observation(1, quality=QualityStatus.DEGRADED)], 10)
    assert poor.sans.probability < good.sans.probability
    assert poor.sans.tier_reason.value == "measurement_quality"
    assert poor.sans.recommended_action.quality_repeat_required
    failed = assess([observation(1, onsd=None, flow=None, quality=QualityStatus.FAILED)], 10)
    assert failed.sans.probability is None
    assert "technical" in failed.sans.recommended_action.text


def test_latest_log_evidence_decays_and_is_not_multiplied():
    first = observation(1)
    history = [first, AstronautDayObservation(astronaut_id="FIXTURE", day=8, metadata=first.metadata)]
    result = assess(history, 10)
    prior = 0.107
    odds = prior / (1 - prior) * 7.2 ** 0.5
    assert result.sans.probability == pytest.approx(odds / (1 + odds))
    assert assess([observation(1), observation(2)], 10).sans.probability == assess([observation(2)], 10).sans.probability


def test_failed_acquisition_retains_consult_and_red_flag_stays_urgent():
    first = observation(1)
    previous = assess([first], 10)
    failed = observation(2, onsd=None, flow=None, quality=QualityStatus.FAILED)
    result = assess([first, failed], 10, previous=previous)
    assert result.sans.tier.value == "consult"
    assert result.sans.measurement_quality.value == "failed"
    assert result.sans.evidence_day == 1
    first.scan_session.measurements[0].red_flag_symptom = True
    urgent = assess([first, failed], 10)
    assert urgent.sans.tier.value == "urgent"
    assert urgent.venous.tier.value != "urgent"


def test_scheduler_input_contains_no_hidden_or_future_information():
    names = {f.name for f in fields(DayView)}
    assert not names.intersection({"case", "sans_onset", "venous_onset", "high", "ground_truth"})
    with pytest.raises(ValueError, match="Future"):
        DayView(2, 1, 1, None, "monitor", "monitor", (3,))
    with pytest.raises(ValueError, match="previously"):
        DayView(2, 3, 1, None, "monitor", "monitor", ())


def test_fixed_anchors_adaptive_replacement_and_precedence():
    fixed_days = [day for day in range(1, 31) if decide(DayView(day, None, None, None, "monitor", "monitor", ()), "fixed")[0]]
    assert fixed_days == [1, 8, 15, 22, 29]
    view = DayView(8, 1, 1, None, "monitor", "monitor", ())
    assert decide(view, "adaptive_replacement") == (False, "routine_deferred")
    assert decide(replace(view, day=15), "adaptive_replacement") == (True, "maximum_gap")
    assert decide(replace(view, day=4, recent_trigger_days=(4,)), "adaptive_replacement") == (True, "observable_trigger")
    assert decide(replace(view, retry_due_day=8, sans_tier="urgent"), "adaptive_replacement") == (True, "failed_acquisition_retry")


def test_shared_sessions_retry_and_policy_exclusive_visibility():
    case = make_case("FIXTURE", 42, "both")
    fixed, fs, _ = run_case(case, "fixed")
    adaptive, ads, _ = run_case(case, "adaptive_replacement")
    fixed_days = {o.day for o in fixed if o.scan_session}
    adaptive_days = {o.day for o in adaptive if o.scan_session}
    assert fixed_days != adaptive_days
    for history in (fixed, adaptive):
        for obs in history:
            if not obs.scan_session:
                assert measurements_of(obs) == []
                continue
            assert len(measurements_of(obs)) == 2
            if any(m.quality.status != QualityStatus.OK for m in measurements_of(obs)) and not obs.scan_session.is_retry and obs.day < 30:
                assert history[obs.day].scan_session is not None
                assert history[obs.day].scan_session.is_retry
    for day in fixed_days & adaptive_days:
        assert fixed[day - 1].scan_session.measurements == adaptive[day - 1].scan_session.measurements
    forbidden = {"sans_onset", "venous_onset", "scenario_label", "high", "has_sans_event"}
    for row in fixed:
        assert not forbidden.intersection(json.loads(row.model_dump_json()))
    assert all(a.sans.evidence_day is None or a.sans.evidence_day <= a.as_of_day for a in ads + fs)


def test_real_engineering_metrics_are_reproducible_and_labeled(tmp_path):
    a = study(tmp_path / "a", engineering_fixture=True, crew_size=4, seeds=(42, 43), sensitivities=[0.5, 0.9], half_lives=[7])
    b = study(tmp_path / "b", engineering_fixture=True, crew_size=4, seeds=(42, 43), sensitivities=[0.5, 0.9], half_lives=[7])
    assert a == b
    assert a["validated_for_experiment"] is False
    assert len(a["rows"]) == 8
    for row in a["rows"]:
        assert row["successful_measurements"] + row["failed_measurements"] + row["degraded_measurements"] == row["sessions"] * 2
        for outcome in ("sans", "venous"):
            assert row[outcome]["synthetic_events"] == row[outcome]["detected_events"] + row[outcome]["missed_events"]
            assert sum(row[outcome]["tier_distribution"].values()) == 120


def test_urgent_follow_up_participates_in_the_actual_causal_loop():
    case = make_case("URGENT-FIXTURE", 42, "healthy")
    history, assessments, decisions = run_case(case, "adaptive_replacement", explicit_red_flag_days=(1,))
    assert assessments[0].sans.tier.value == "urgent"
    assert all(o.scan_session is not None for o in history)
    assert all(d["reason"] in {"mission_start", "urgent_follow_up", "failed_acquisition_retry"} for d in decisions)


def test_production_publication_rejects_fixture_before_modifying_destination(tmp_path):
    from prepare_public_run import prepare
    from publish_frontend_demo_data import publish
    prepare(tmp_path / "source", crew_size=4)
    source, target = tmp_path / "source", tmp_path / "public"
    target.mkdir()
    sentinel = target / "crew_observations.jsonl"
    sentinel.write_text("preserved")
    path = source / "crew_observations.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["metadata"]["synthetic_label"] = SPEC["label"]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="Engineering fixtures"):
        publish(source, target)
    assert sentinel.read_text() == "preserved"


def test_active_monitoring_retains_serious_alert_after_failed_shared_scan():
    from monitoring.engine import assess_history
    from registry.loader import load_all, Registry
    registry = load_all()
    # This LR is ONLY an explicit engineering input exercising precedence. The
    # real approved retrograde LR=10 cannot reach Consult from a 5% prior.
    mapping = registry.assumptions["jugular_flow_risk_mapping"].model_copy(update={"value_or_range": {
        **registry.assumptions["jugular_flow_risk_mapping"].value_or_range,
        "flow_class_likelihood_ratios": {"antegrade": 0.3, "stagnant": 4, "retrograde": 20}}})
    fixture_registry = Registry(parameters=registry.parameters, assumptions={**registry.assumptions, "jugular_flow_risk_mapping": mapping})
    first = observation(1, flow="retrograde")
    failed = observation(2, onsd=None, flow=None, quality=QualityStatus.FAILED)
    result = assess_history([first, failed], fixture_registry)
    assert result.venous.tier.value == "consult"
    assert result.venous.measurement_quality == QualityStatus.FAILED
    assert result.venous.evidence_day == 1
    assert result.venous.recommended_action.quality_repeat_required


def test_legacy_evaluation_masks_unrequested_shared_sessions():
    from evaluation.sweep import ObservableCase, _build_policy_day_view
    source = ObservableCase(case_id="FIXTURE", days=[1, 2, 3], observations_by_day={d: observation(d) for d in [1, 2, 3]})
    visible = source.visible_history(2, {1})
    assert visible[0].scan_session is not None
    assert visible[1].scan_session is None
    view = _build_policy_day_view(source, 2, [1], {"sans": "monitor", "venous": "monitor"})
    assert set(view.acquired_sessions_by_day) == {1}
    assert source.observations_by_day[2].scan_session is not None


def test_readable_degraded_evidence_cannot_clear_existing_consult():
    first = observation(1)
    previous = assess([first], 10)
    second = observation(2, quality=QualityStatus.DEGRADED)
    result = assess([first, second], 10, previous=previous)
    assert result.sans.probability < previous.sans.probability
    assert result.sans.tier.value == "consult"
    assert result.sans.tier_reason.value == "persistent_serious_evidence"
    assert result.sans.recommended_action.quality_repeat_required
