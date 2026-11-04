"""evaluation/plotting.py tests. All data here is an ENGINEERING FIXTURE, labeled
as such on the rendered chart - never a scientific finding."""
from __future__ import annotations

from evaluation.plotting import extract_series, plot_metric
from evaluation.sweep import OutcomeMetrics, PolicyRunResult, ScanAccounting


def _result(policy, scans_by_case):
    per_case = {
        case_id: {
            "sans": OutcomeMetrics(
                scans_used=scans,
                scan_accounting=ScanAccounting(requested=scans, data_available=0, valid=0, degraded_or_unknown=0, unavailable=scans),
                detection_delay=None, missed_event=False, false_escalations=0, falsely_escalated=False,
            )
        }
        for case_id, scans in scans_by_case.items()
    }
    return PolicyRunResult(policy=policy, per_case=per_case)


def _fixture_points():
    return [
        {"assumed_trigger_accuracy": 0.3, "fixed": _result("fixed", {"A1": 5, "A2": 5}), "adaptive": _result("adaptive", {"A1": 9, "A2": 9})},
        {"assumed_trigger_accuracy": 0.9, "fixed": _result("fixed", {"A1": 5, "A2": 5}), "adaptive": _result("adaptive", {"A1": 3, "A2": 3})},
    ]


def test_extract_series_reads_totals_per_outcome():
    points = _fixture_points()
    xs, fixed_vals, adaptive_vals = extract_series(points, "sans", "scans_used")
    assert xs == [0.3, 0.9]
    assert fixed_vals == [10.0, 10.0]
    assert adaptive_vals == [18.0, 6.0]


def test_plot_metric_writes_png_and_detects_crossover(tmp_path):
    points = _fixture_points()
    output_path = tmp_path / "fixture_crossover.png"
    crossover = plot_metric(points, "sans", "scans_used", output_path, fixture_label="ENGINEERING FIXTURE")
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert crossover is not None
    assert 0.3 < crossover < 0.9


def test_plot_metric_rejects_unknown_metric(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        plot_metric(_fixture_points(), "sans", "not_a_real_metric", tmp_path / "x.png")
