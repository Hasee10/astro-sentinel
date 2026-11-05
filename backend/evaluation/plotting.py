"""Milestone B: render the trigger-accuracy sweep as a comparison chart.

This module is pure rendering - it NEVER invents data. `evaluate_policies.py` only
calls it after a real `run_sweep()` has produced genuine computed values from the
real registry and the real `assess_history()` engine. Tests may call it directly on
engineering-fixture sweep results to verify the rendering math, but such fixture
output must never be shown as a scientific finding - see tests/test_plotting.py's
explicit "ENGINEERING FIXTURE" labeling convention.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Sequence

import matplotlib

matplotlib.use("Agg")  # headless: this module never opens a display window
import matplotlib.pyplot as plt

from evaluation.sweep import PolicyRunResult, find_crossover

# metric name -> (extractor over a PolicyRunResult, lower_is_better)
METRIC_SPECS: dict[str, tuple[Callable[[PolicyRunResult, str], Optional[float]], bool]] = {
    "scans_used": (lambda r, outcome: float(r.total_scans(outcome)), True),
    "mean_detection_delay": (lambda r, outcome: r.mean_detection_delay(outcome), True),
    "missed_events": (lambda r, outcome: float(r.total_missed_events(outcome)), True),
    "false_escalations": (lambda r, outcome: float(r.total_false_escalations(outcome)), True),
}


def extract_series(
    points: Sequence[dict], outcome: str, metric: str
) -> tuple[list[float], list[Optional[float]], list[Optional[float]]]:
    """points: the list[dict] returned by evaluation.sweep.run_sweep()."""
    if metric not in METRIC_SPECS:
        raise ValueError(f"unknown metric {metric!r}; choose one of {sorted(METRIC_SPECS)}")
    extractor, _ = METRIC_SPECS[metric]
    xs = [p["assumed_trigger_accuracy"] for p in points]
    fixed_vals = [extractor(p["fixed"], outcome) for p in points]
    adaptive_vals = [extractor(p["adaptive"], outcome) for p in points]
    return xs, fixed_vals, adaptive_vals


def plot_metric(
    points: Sequence[dict],
    outcome: str,
    metric: str,
    output_path: Path,
    fixture_label: Optional[str] = None,
    pilot_label: Optional[str] = None,
) -> Optional[float]:
    """Plots one outcome/metric pair: fixed vs. adaptive across the swept x-axis.

    Returns the crossover x-value (None if the curves never cross, or if either
    series contains a None point and no crossover can be computed). `fixture_label`,
    when set, is stamped on the chart title so an engineering-fixture plot can never
    be mistaken for a real research result. `pilot_label` is the separate,
    real-result case (see evaluation.experiment_readiness.SANS_ONLY_PILOT_LABEL):
    a genuine computed result that is nonetheless partial (e.g. SANS-only, venous
    excluded) - stamped distinctly from `fixture_label` so a pilot result is never
    confused with throwaway test fixture output, or silently read as the full study.
    """
    xs, fixed_vals, adaptive_vals = extract_series(points, outcome, metric)
    _, lower_is_better = METRIC_SPECS[metric]

    crossover = None
    if all(v is not None for v in fixed_vals) and all(v is not None for v in adaptive_vals):
        crossover = find_crossover(xs, fixed_vals, adaptive_vals, lower_is_better=lower_is_better)  # type: ignore[arg-type]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs, fixed_vals, marker="o", label="fixed schedule")
    ax.plot(xs, adaptive_vals, marker="o", label="adaptive schedule")
    if crossover is not None:
        ax.axvline(crossover, linestyle="--", color="gray", label=f"crossover @ {crossover:.3f}")

    title = f"{outcome.upper()} - {metric} vs. assumed trigger accuracy (SYNTHETIC DATA)"
    if pilot_label:
        title = f"[{pilot_label}] {title}"
    if fixture_label:
        title = f"[{fixture_label}] {title}"
    ax.set_title(title)
    ax.set_xlabel("Assumed trigger accuracy/usefulness (simulation-design parameter, not a clinical measure)")
    ax.set_ylabel(metric)
    ax.legend()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return crossover
