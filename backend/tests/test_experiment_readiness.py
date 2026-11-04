"""ASTROSENTINEL correction (2026-11-04), Part 1: evaluation/experiment_readiness.py.

The core regression this file guards: `has_sans_event=True, sans_onset_day=None`
must never be scored as a confirmed-healthy "0 missed events" - it must block the
experiment instead, with the reason explicit.
"""
from __future__ import annotations

from evaluation.experiment_readiness import (
    EventGroundTruthStatus,
    check_experiment_readiness,
    sans_ground_truth_status,
    summarize_ground_truth,
    venous_ground_truth_status,
)
from evaluation.sweep import HiddenGroundTruth, ObservableCase, SweepCase


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


# ---- cohort summary / readiness ----


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


def test_check_experiment_readiness_blocks_on_unknown_onset_not_zero_missed():
    """The exact regression: a cohort with an unresolved SANS case must report
    ready=False with an explicit sans_detection_metrics blocker - never silently
    pass through to a "0 missed events" result."""
    cohort = [_case("A", has_sans_event=True, sans_onset_day=None)]
    report = check_experiment_readiness(cohort)
    assert report.ready is False
    assert any(b.capability == "sans_detection_metrics" for b in report.blockers)
    assert "confirmed as healthy" not in str(report.blockers).lower()  # never phrased as a healthy determination


def test_check_experiment_readiness_blocks_on_venous_always():
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]  # SANS fully resolved
    report = check_experiment_readiness(cohort)
    assert report.ready is False  # venous alone is enough
    capabilities = {b.capability for b in report.blockers}
    assert "venous_detection_metrics" in capabilities
    assert "sans_detection_metrics" not in capabilities  # SANS specifically did NOT block


def test_check_experiment_readiness_ready_true_only_for_fully_resolved_sans_fixture():
    """Still blocked overall (venous), but proves the function can in principle
    report SANS-clean - engineering fixture, not a claim that this is approved."""
    cohort = [
        _case("A", has_sans_event=False, sans_onset_day=None),
        _case("B", has_sans_event=True, sans_onset_day=15),
    ]
    report = check_experiment_readiness(cohort)
    assert report.ground_truth_summary["sans"] == {"confirmed_none": 1, "confirmed_with_onset": 1}
    assert not any(b.capability == "sans_detection_metrics" for b in report.blockers)


def test_empty_cohort_reports_ready_trivially():
    report = check_experiment_readiness([])
    assert report.ready is True
    assert report.blockers == []


def test_readiness_report_never_fabricates_a_count_for_missing_data():
    """ground_truth_summary must reflect only cases actually present - it does not
    pad in zeros for statuses that didn't occur."""
    cohort = [_case("A", has_sans_event=False, sans_onset_day=None)]
    report = check_experiment_readiness(cohort)
    assert report.ground_truth_summary["sans"] == {"confirmed_none": 1}
    assert "event_unknown_onset" not in report.ground_truth_summary["sans"]
