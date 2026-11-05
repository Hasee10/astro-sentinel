"""ASTROSENTINEL correction (2026-11-04), Part 1 + same-day extension ("approving
onset timing alone cannot produce an apparently valid full experiment").

The core regressions this file guards:
1. has_sans_event=True, sans_onset_day=None must never be scored as a
   confirmed-healthy "0 missed events" - it must block the experiment instead,
   with the reason explicit (Part 1, the original defect).
2. Even a cohort with PERFECT ground-truth consistency must still block if no
   physiological progression model, no authorized monitoring rule, or (for
   venous) no event-occurrence/onset model exists - resolving onset timing
   alone can never make an experiment read as fully ready (the extension).
"""
from __future__ import annotations

from dataclasses import replace

import evaluation.experiment_readiness as er_module
from evaluation.experiment_readiness import (
    EventGroundTruthStatus,
    check_adaptive_replacement_authorized,
    check_experiment_readiness,
    sans_ground_truth_status,
    summarize_ground_truth,
    venous_ground_truth_status,
)
from evaluation.sweep import HiddenGroundTruth, ObservableCase, SweepCase
from registry.design_decisions import DesignDecision
from registry.loader import load_all


def _case(case_id: str, **gt_kwargs) -> SweepCase:
    return SweepCase(
        observable=ObservableCase(case_id=case_id, days=list(range(1, 31))),
        ground_truth=HiddenGroundTruth(case_id=case_id, **gt_kwargs),
    )


# ---- sans_ground_truth_status: the exact 4-way classification ----


def test_confirmed_none_is_a_genuine_healthy_case():
    status = sans_ground_truth_status(HiddenGroundTruth(case_id="A", has_sans_event=False, sans_onset_day=None))
    assert status == EventGroundTruthStatus.CONFIRMED_NONE


def test_confirmed_with_onset_when_both_fields_agree():
    status = sans_ground_truth_status(HiddenGroundTruth(case_id="A", has_sans_event=True, sans_onset_day=12))
    assert status == EventGroundTruthStatus.CONFIRMED_WITH_ONSET


def test_event_unknown_onset_is_the_reported_bug_exactly():
    """has_sans_event=True, sans_onset_day=None - today's actual real-data state
    for every SANS-event astronaut, since onset-day assignment is unapproved."""
    status = sans_ground_truth_status(HiddenGroundTruth(case_id="A", has_sans_event=True, sans_onset_day=None))
    assert status == EventGroundTruthStatus.EVENT_UNKNOWN_ONSET


def test_undetermined_when_event_flag_itself_is_missing():
    status = sans_ground_truth_status(HiddenGroundTruth(case_id="A", has_sans_event=None, sans_onset_day=None))
    assert status == EventGroundTruthStatus.UNDETERMINED


def test_undetermined_on_inconsistent_data_no_event_but_onset_set():
    """has_sans_event=False with a non-null onset day is internally inconsistent -
    flagged, never silently trusting one field over the other."""
    status = sans_ground_truth_status(HiddenGroundTruth(case_id="A", has_sans_event=False, sans_onset_day=5))
    assert status == EventGroundTruthStatus.UNDETERMINED


def test_venous_is_always_undetermined_regardless_of_data():
    """No venous event-occurrence model is approved at all - not a per-case data
    gap, so no venous ground truth record can ever read as resolved today."""
    for gt in (
        HiddenGroundTruth(case_id="A"),
        HiddenGroundTruth(case_id="A", venous_onset_day=5),
        HiddenGroundTruth(case_id="A", venous_onset_day=None),
    ):
        assert venous_ground_truth_status(gt) == EventGroundTruthStatus.UNDETERMINED


# ---- cohort summary (summarize_ground_truth takes no registry - unaffected) ----


def test_cohort_fully_resolved_only_when_no_unresolved_statuses():
    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=10),
    ]
    summary = summarize_ground_truth(cohort, "sans")
    assert summary.is_fully_resolved is True


def test_cohort_not_resolved_with_even_one_unknown_onset_case():
    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=10),
        _case("C", has_sans_event=True, sans_onset_day=None),  # the one bad case
    ]
    summary = summarize_ground_truth(cohort, "sans")
    assert summary.is_fully_resolved is False
    assert summary.counts["event_unknown_onset"] == 1


# ---- check_experiment_readiness: check 1, ground-truth consistency ----


def test_check_experiment_readiness_blocks_on_unknown_onset_not_zero_missed():
    """The exact Part-1 regression: a cohort with an unresolved SANS case must
    report a sans_ground_truth_consistency blocker - never silently pass through
    to a "0 missed events" result."""
    cohort = [_case("A", has_sans_event=True, sans_onset_day=None)]
    report = check_experiment_readiness(cohort, load_all())
    assert report.ready is False
    assert any(b.capability == "sans_ground_truth_consistency" for b in report.blockers)
    assert "confirmed as healthy" not in str(report.blockers).lower()


def test_check_experiment_readiness_blocks_on_venous_ground_truth_always():
    """No venous event-occurrence model is approved - venous_ground_truth_consistency
    fires for every cohort, regardless of SANS's own ground-truth state."""
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]  # SANS ground truth fully resolved
    report = check_experiment_readiness(cohort, load_all())
    assert report.ready is False
    capabilities = {b.capability for b in report.blockers}
    assert "venous_ground_truth_consistency" in capabilities
    # the GROUND-TRUTH check specifically did not fire for SANS (other SANS
    # checks still block today - see test_resolving_onset_timing_alone_... below).
    assert "sans_ground_truth_consistency" not in capabilities


def test_sans_ground_truth_check_clears_independently_of_other_sans_checks():
    """Proves check 1 resolves per-outcome, independently of checks 2-3: a
    fully-resolved SANS cohort clears sans_ground_truth_consistency specifically -
    this does NOT mean SANS overall is ready (see test_resolving_onset_timing_
    alone_does_not_produce_an_apparently_valid_experiment below)."""
    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=15),
    ]
    report = check_experiment_readiness(cohort, load_all())
    assert report.ground_truth_summary["sans"] == {"confirmed_none": 1, "confirmed_with_onset": 1}
    assert not any(b.capability == "sans_ground_truth_consistency" for b in report.blockers)


def test_empty_cohort_still_blocks_on_capability_readiness():
    """An empty cohort trivially satisfies ground-truth consistency (vacuously -
    there are no unresolved cases) for BOTH outcomes, but checks 2-4 are about
    registry/model-readiness STATE, not cohort contents - they fire regardless of
    how many cases exist. 'No ground-truth problem' must never be confused with
    'ready': the experiment is correctly still blocked."""
    report = check_experiment_readiness([], load_all())
    assert report.ground_truth_summary["sans"] == {}
    assert report.ground_truth_summary["venous"] == {}
    assert report.ready is False
    capabilities = {b.capability for b in report.blockers}
    assert "sans_ground_truth_consistency" not in capabilities
    assert "venous_ground_truth_consistency" not in capabilities
    assert "sans_physiological_progression" in capabilities
    assert "sans_monitoring_rule" in capabilities


def test_readiness_report_never_fabricates_a_count_for_missing_data():
    """ground_truth_summary must reflect only cases actually present - it does not
    pad in zeros for statuses that didn't occur."""
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]
    report = check_experiment_readiness(cohort, load_all())
    assert report.ground_truth_summary["sans"] == {"confirmed_none": 1}
    assert "event_unknown_onset" not in report.ground_truth_summary["sans"]


# ---- the explicit regression: onset timing alone is not sufficient ----


def test_resolving_onset_timing_alone_does_not_produce_an_apparently_valid_experiment(monkeypatch):
    """The exact scenario the correction asks to guard against: even a cohort
    with FULLY RESOLVED SANS onset-timing ground truth (as if
    sans_venous_onset_day_assignment were both approved and implemented) still
    blocks, because sans_physiological_progression (WHAT HAPPENS, not WHEN) and
    sans_monitoring_rule are independent capabilities - onset-day placement says
    nothing about either of them. Approving the onset DECISION itself changes
    nothing about them either, since they are tracked under entirely separate
    design-decision ids."""
    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=10),
        _case("C", has_sans_event=True, sans_onset_day=22),
    ]
    registry = load_all()

    report = check_experiment_readiness(cohort, registry)
    capabilities = {b.capability for b in report.blockers}
    assert "sans_ground_truth_consistency" not in capabilities  # onset timing: fully resolved
    assert "sans_physiological_progression" in capabilities  # WHAT HAPPENS: still blocked
    assert "sans_monitoring_rule" in capabilities  # detection formula: still blocked
    assert report.ready is False

    approved_onset_decision = DesignDecision(
        decision_id="sans_venous_onset_day_assignment",
        description="test",
        approved=True,
        decision_text="Use a fixed onset day.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "sans_venous_onset_day_assignment", approved_onset_decision)
    report_after = check_experiment_readiness(cohort, registry)
    capabilities_after = {b.capability for b in report_after.blockers}
    assert "sans_physiological_progression" in capabilities_after
    assert "sans_monitoring_rule" in capabilities_after
    assert report_after.ready is False


# ---- venous eligibility: three named conditions, checked separately ----


def test_venous_eligibility_lists_all_missing_conditions():
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]
    report = check_experiment_readiness(cohort, load_all())
    eligibility_blockers = [b for b in report.blockers if b.capability == "venous_eligibility_conditions"]
    assert len(eligibility_blockers) == 1
    message = eligibility_blockers[0].message
    assert "event_occurrence_model_approved" in message
    assert "onset_model_approved" in message
    assert "measurement_generation_implemented" in message


def test_venous_eligibility_clears_only_once_all_three_conditions_are_met(monkeypatch):
    """A partial fix (e.g. only the onset model approved) must stay visible as a
    partial fix, not read as venous being ready."""
    import simulation.generation_models as gm_module

    onset_decision = DesignDecision(
        decision_id="sans_venous_onset_day_assignment",
        description="test",
        approved=True,
        decision_text="Use a fixed onset day.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "sans_venous_onset_day_assignment", onset_decision)
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]
    report_partial = check_experiment_readiness(cohort, load_all())
    assert any(b.capability == "venous_eligibility_conditions" for b in report_partial.blockers)

    event_decision = DesignDecision(
        decision_id="venous_event_occurrence_model",
        description="test",
        approved=True,
        decision_text="Fixed cohort-wide event rate.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "venous_event_occurrence_model", event_decision)
    monkeypatch.setitem(
        gm_module.GENERATION_MODEL_SPECS,
        "jugular_scan_values",
        replace(gm_module.GENERATION_MODEL_SPECS["jugular_scan_values"], has_implemented_rule=True),
    )
    report_full = check_experiment_readiness(cohort, load_all())
    assert not any(b.capability == "venous_eligibility_conditions" for b in report_full.blockers)


# ---- adaptive-replacement scheduling authorization (opt-in only) ----


def test_adaptive_replacement_unauthorized_by_default():
    authorized, blocker = check_adaptive_replacement_authorized(load_all())
    assert authorized is False
    assert blocker is not None
    assert blocker.capability == "adaptive_replacement_scheduling"


def test_approving_the_decision_alone_still_blocks_without_execution_wiring(monkeypatch):
    """Round-3 correction ('do not merely flip an approval boolean'): approving
    adaptive_scheduling_policy_semantics ALONE must never read as authorized -
    evaluation.sweep.run_sweep() would still silently execute the original
    AdaptiveSchedulePolicy underneath it, which is exactly the false
    'scan-saving' claim this dual gate exists to prevent."""
    import evaluation.sweep as sweep_module

    approved_decision = DesignDecision(
        decision_id="adaptive_scheduling_policy_semantics",
        description="test",
        approved=True,
        decision_text="Option B, max_gap_days=5, defer_lookback_days=3.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "adaptive_scheduling_policy_semantics", approved_decision)
    monkeypatch.setattr(sweep_module, "ADAPTIVE_REPLACEMENT_EXECUTION_WIRED", False)

    authorized, blocker = check_adaptive_replacement_authorized(load_all())
    assert authorized is False
    assert blocker is not None
    assert "no wired, tested execution path" in blocker.message


def test_adaptive_replacement_authorized_only_once_both_conditions_hold(monkeypatch):
    """The real unblock condition is BOTH approval AND a wired, tested execution
    path - neither alone is enough (see the two tests immediately around this
    one)."""
    import evaluation.sweep as sweep_module

    approved_decision = DesignDecision(
        decision_id="adaptive_scheduling_policy_semantics",
        description="test",
        approved=True,
        decision_text="Option B, max_gap_days=5, defer_lookback_days=3.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "adaptive_scheduling_policy_semantics", approved_decision)
    monkeypatch.setattr(sweep_module, "ADAPTIVE_REPLACEMENT_EXECUTION_WIRED", True)

    authorized, blocker = check_adaptive_replacement_authorized(load_all())
    assert authorized is True
    assert blocker is None


def test_execution_wiring_alone_without_approval_still_blocks(monkeypatch):
    """The reverse half of the dual gate: even a (hypothetically) wired execution
    path must not bypass the research-lead's own decision approval."""
    import evaluation.sweep as sweep_module

    monkeypatch.setattr(sweep_module, "ADAPTIVE_REPLACEMENT_EXECUTION_WIRED", True)
    authorized, blocker = check_adaptive_replacement_authorized(load_all())
    assert authorized is False
    assert blocker is not None
    assert "not fully approved" in blocker.message


def test_run_sweep_has_no_policy_selection_parameter():
    """Structural guard for 'do not implement unfinished medical scheduling
    semantics just to enable the CLI flag' / 'replacement flag never executes
    old policy while claiming replacement semantics': run_sweep() has, on
    purpose, no parameter whatsoever that could select
    AdaptiveReplacementSchedulePolicy - it always builds AdaptiveSchedulePolicy
    (FIXED BACKSTOP + TRIGGERED EXTRA SCANS) for the 'adaptive' row, and there
    is nothing here for any flag to influence."""
    import inspect

    from evaluation.sweep import run_sweep

    params = set(inspect.signature(run_sweep).parameters)
    assert params == {"accuracy_values", "cohort", "trigger_fired_fn", "fixed_interval_days", "tier_fn", "registry"}


def test_use_adaptive_replacement_is_opt_in_and_never_activates_by_default():
    """Requesting nothing (the default) never adds the blocker, even though it
    would fire if requested - this check never runs unless explicitly asked for."""
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]
    registry = load_all()

    report_default = check_experiment_readiness(cohort, registry)
    assert not any(b.capability == "adaptive_replacement_scheduling" for b in report_default.blockers)

    report_requested = check_experiment_readiness(cohort, registry, use_adaptive_replacement=True)
    assert any(b.capability == "adaptive_replacement_scheduling" for b in report_requested.blockers)
    assert report_requested.ready is False


# ---- SANS-only pilot mode: opt-in, never premature, never silent ----


def test_pilot_mode_never_activates_while_sans_has_its_own_blockers():
    """Today SANS always has its own blockers (progression/monitoring-rule are
    unimplemented) - allow_sans_only_pilot must not override that, no matter how
    clean the ground truth is."""
    cohort = [_case("A", has_sans_event=True, sans_onset_day=10)]
    report = check_experiment_readiness(cohort, load_all(), allow_sans_only_pilot=True)
    assert report.is_pilot is False
    assert report.ready is False


def test_pilot_mode_activates_once_sans_independently_clears(monkeypatch):
    """Infrastructure test: once SANS's progression and monitoring-rule
    capabilities are BOTH simulated as ready (not approved/implemented for real
    today), an allow_sans_only_pilot=True caller gets ready=True with
    is_pilot=True and an explicit pilot_label - and venous's blockers are KEPT
    (not dropped), never silently presented as resolved."""
    import monitoring.engine as engine_module
    import simulation.generation_models as gm_module

    approved_progression_decision = DesignDecision(
        decision_id="sans_physiological_progression",
        description="test",
        approved=True,
        decision_text="Linear ramp over 5 days to a fixed target magnitude.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "sans_physiological_progression", approved_progression_decision)
    monkeypatch.setitem(
        gm_module.GENERATION_MODEL_SPECS,
        "sans_physiological_progression",
        replace(gm_module.GENERATION_MODEL_SPECS["sans_physiological_progression"], has_implemented_rule=True),
    )
    monkeypatch.setattr(engine_module, "MONITORING_PROBABILITY_IMPLEMENTED", {"sans", "venous"})

    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=10),
    ]
    report = check_experiment_readiness(cohort, load_all(), allow_sans_only_pilot=True)
    assert report.ready is True
    assert report.is_pilot is True
    assert report.pilot_label == er_module.SANS_ONLY_PILOT_LABEL
    assert report.blockers  # venous blockers kept, not dropped
    assert all(b.capability.startswith("venous") for b in report.blockers)
    assert not any(b.capability.startswith("sans") for b in report.blockers)


def test_pilot_mode_never_bypasses_an_unapproved_global_blocker(monkeypatch):
    """The exact round-3 regression ('fix pilot-mode authorization bypass'):
    SANS progression/monitoring-rule cleared (as above), venous blocked, AND
    adaptive replacement explicitly requested while unapproved - all in the
    SAME call. Before this fix, the pilot branch only inspected
    sans_blockers/venous_blockers and ignored that the combined blocker list
    also carried the adaptive-replacement blocker, so it could return
    ready=True and silently drop that blocker from the report. A global
    blocker's scope is the whole experiment, not 'the venous half of it', so
    pilot mode must never activate while one is outstanding."""
    import monitoring.engine as engine_module
    import simulation.generation_models as gm_module

    approved_progression_decision = DesignDecision(
        decision_id="sans_physiological_progression",
        description="test",
        approved=True,
        decision_text="Linear ramp over 5 days to a fixed target magnitude.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "sans_physiological_progression", approved_progression_decision)
    monkeypatch.setitem(
        gm_module.GENERATION_MODEL_SPECS,
        "sans_physiological_progression",
        replace(gm_module.GENERATION_MODEL_SPECS["sans_physiological_progression"], has_implemented_rule=True),
    )
    monkeypatch.setattr(engine_module, "MONITORING_PROBABILITY_IMPLEMENTED", {"sans", "venous"})
    # adaptive_scheduling_policy_semantics and ADAPTIVE_REPLACEMENT_EXECUTION_WIRED
    # are both deliberately left at their real, unapproved/unwired defaults.

    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=10),
    ]
    report = check_experiment_readiness(
        cohort, load_all(), allow_sans_only_pilot=True, use_adaptive_replacement=True
    )

    assert report.is_pilot is False  # pilot must NOT activate
    assert report.ready is False  # the whole experiment stays blocked
    capabilities = {b.capability for b in report.blockers}
    assert "adaptive_replacement_scheduling" in capabilities  # never silently dropped
    assert not any(b.capability.startswith("sans") for b in report.blockers)  # SANS itself is still clean


def test_pilot_mode_is_opt_in_and_off_by_default(monkeypatch):
    """The same cleared-SANS state as above, but WITHOUT allow_sans_only_pilot -
    must stay blocked overall (never silently default into pilot mode)."""
    import monitoring.engine as engine_module
    import simulation.generation_models as gm_module

    approved_progression_decision = DesignDecision(
        decision_id="sans_physiological_progression",
        description="test",
        approved=True,
        decision_text="Linear ramp over 5 days to a fixed target magnitude.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "sans_physiological_progression", approved_progression_decision)
    monkeypatch.setitem(
        gm_module.GENERATION_MODEL_SPECS,
        "sans_physiological_progression",
        replace(gm_module.GENERATION_MODEL_SPECS["sans_physiological_progression"], has_implemented_rule=True),
    )
    monkeypatch.setattr(engine_module, "MONITORING_PROBABILITY_IMPLEMENTED", {"sans", "venous"})

    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]
    report = check_experiment_readiness(cohort, load_all())  # allow_sans_only_pilot defaults False
    assert report.ready is False
    assert report.is_pilot is False
