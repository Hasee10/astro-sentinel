#!/usr/bin/env python
"""Deliverable 3's executable entry point: adaptive-vs-fixed comparison + trigger-
accuracy sweep, run through the real monitoring engine.

Loads validated synthetic observations and the evaluation-only ground-truth channel
SEPARATELY (never merging hidden onset days into anything a scheduling/tier decision
can see - see evaluation/sweep.py's ObservableCase/HiddenGroundTruth split), checks
TWO independent gates - `evaluation.sweep.sweep_blockers()` (are the right
assumptions/decisions approved?) AND `evaluation.experiment_readiness
.check_experiment_readiness()` (is the resulting DATA actually usable for these
metrics - ASTROSENTINEL correction, 2026-11-04: an approved registry does not imply
a complete ground truth; `has_sans_event=True, sans_onset_day=None` must never be
scored as a confirmed-healthy "0 missed events") - and either:

- both gates pass: runs both policies through the same `monitoring.engine.assess_history()`
  call for every swept trigger-accuracy value, saves adaptive_vs_fixed.csv/.json and
  trigger_accuracy_sweep.csv, and renders trigger_accuracy_crossover.png per outcome
  per metric; or
- either gate fails (true for every run today - see the research-lead blocker
  handoff), writes evaluation_blockers.json and stops. No CSV or PNG is ever written
  for a blocked run - this script does not fabricate a crossover, nor treat an
  unresolved ground-truth gap as a valid result, to make the "main research result"
  appear complete.

Example:
    python evaluate_policies.py --observations outputs/run1/crew_observations.jsonl \\
        --ground-truth outputs/run1/ground_truth.jsonl --output-dir outputs/run1/eval
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from contracts.models import AstronautDayObservation, BlockerReport, GroundTruthRecord
from evaluation.experiment_readiness import check_experiment_readiness
from evaluation.plotting import plot_metric
from evaluation.sweep import (
    HiddenGroundTruth,
    ObservableCase,
    PolicyDayView,
    PolicyRunResult,
    SweepCase,
    make_engine_tier_fn,
    run_sweep,
    sweep_blockers,
)
from evaluation.trigger_model import build_trigger_schedules, make_precomputed_trigger_fn
from registry.loader import Registry, load_all

OUTCOME_METRICS = ["scans_used", "mean_detection_delay", "missed_events", "false_escalations"]


def _read_jsonl(path: Path, model) -> list:
    records = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(model.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"{path}:{line_no}: invalid record: {exc}") from exc
    return records


def build_cohort(observations_path: Path, ground_truth_path: Path) -> list[SweepCase]:
    """Loads the two JSONL channels SEPARATELY and only pairs them up into a
    SweepCase container - the scheduling/tier path (run_sweep) still only ever
    receives `.observable`, never `.ground_truth`, until metric-scoring time."""
    observations = _read_jsonl(observations_path, AstronautDayObservation)
    ground_truth_records = _read_jsonl(ground_truth_path, GroundTruthRecord)

    by_astronaut: dict[str, list[AstronautDayObservation]] = defaultdict(list)
    for obs in observations:
        by_astronaut[obs.astronaut_id].append(obs)
    gt_by_astronaut: dict[str, GroundTruthRecord] = {g.astronaut_id: g for g in ground_truth_records}

    cohort: list[SweepCase] = []
    for astronaut_id, obs_list in by_astronaut.items():
        obs_sorted = sorted(obs_list, key=lambda o: o.day)
        days = [o.day for o in obs_sorted]
        observable = ObservableCase(
            case_id=astronaut_id,
            days=days,
            observations_by_day={o.day: o for o in obs_sorted},
        )
        gt = gt_by_astronaut.get(astronaut_id)
        ground_truth = HiddenGroundTruth(
            case_id=astronaut_id,
            sans_onset_day=gt.sans_onset_day if gt else None,
            venous_onset_day=gt.venous_onset_day if gt else None,
            has_sans_event=gt.has_sans_event if gt else None,
        )
        cohort.append(SweepCase(observable=observable, ground_truth=ground_truth))
    return cohort


def _comparison_rows(points: list[dict]) -> list[dict]:
    rows = []
    for point in points:
        accuracy = point["assumed_trigger_accuracy"]
        for policy_name in ("fixed", "adaptive"):
            result: PolicyRunResult = point[policy_name]
            for outcome in ("sans", "venous"):
                rows.append(
                    {
                        "assumed_trigger_accuracy": accuracy,
                        "policy": policy_name,
                        "outcome": outcome,
                        "scans_used": result.total_scans(outcome),
                        "scans_with_data": result.total_scans_with_data(outcome),
                        "scans_valid": result.total_scans_valid(outcome),
                        "scans_degraded_or_unknown": result.total_scans_degraded_or_unknown(outcome),
                        "scans_unavailable": result.total_scans_unavailable(outcome),
                        "mean_detection_delay": result.mean_detection_delay(outcome),
                        "missed_events": result.total_missed_events(outcome),
                        "false_escalations": result.total_false_escalations(outcome),
                        "falsely_escalated_astronauts": result.total_falsely_escalated_cases(outcome),
                        "n_cases": len(result.per_case),
                    }
                )
    return rows


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_evaluation(
    observations_path: Path,
    ground_truth_path: Path,
    output_dir: Path,
    fixed_interval_days: Optional[int] = None,
    accuracy_values: Optional[list[float]] = None,
    registry: Optional[Registry] = None,
    trigger_seed: int = 0,
) -> dict[str, Path]:
    """The real pipeline. `fixed_interval_days`/`accuracy_values` are read from the
    approved `fixed_schedule_interval_choice` / `hrv_trigger_assumed_accuracy`
    assumptions when not given explicitly - an explicit override here is for tests
    against an in-memory fixture registry only; `main()` never passes one against
    the real registry, since doing so would bypass the approval gate this script
    exists to enforce.
    """
    registry = registry or load_all()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Gate 1: are the right assumptions/decisions approved at all?
    blockers = sweep_blockers(registry)

    # Gate 2 (ASTROSENTINEL correction): independent of Gate 1 - is the ground
    # truth on hand actually usable for the metrics about to be computed? Built
    # regardless of Gate 1's outcome so both reports are complete in one pass.
    cohort = build_cohort(observations_path, ground_truth_path)
    readiness = check_experiment_readiness(cohort)
    blockers = blockers + readiness.blockers

    if blockers:
        report = BlockerReport(run_id="evaluate_policies", stage="evaluate_policies", blockers=blockers)
        blockers_path = output_dir / "evaluation_blockers.json"
        blockers_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        summary_path = output_dir / "experiment_readiness_summary.json"
        summary_path.write_text(
            json.dumps({"ground_truth_summary": readiness.ground_truth_summary}, indent=2), encoding="utf-8"
        )
        return {"blockers": blockers_path, "readiness_summary": summary_path}

    if fixed_interval_days is None:
        interval_config = registry.assumptions["fixed_schedule_interval_choice"].value_or_range
        fixed_interval_days = interval_config["primary_interval_days"]  # type: ignore[index]
    if accuracy_values is None:
        trigger_config = registry.assumptions["hrv_trigger_assumed_accuracy"].value_or_range
        accuracy_values = trigger_config["sweep"]  # type: ignore[index]

    tier_fn = make_engine_tier_fn(registry)

    trigger_config = registry.assumptions["hrv_trigger_assumed_accuracy"].value_or_range
    schedules = build_trigger_schedules(
        cohort=[(case.observable, case.ground_truth) for case in cohort],
        accuracy_values=accuracy_values,
        base_false_fire_probability=trigger_config["base_false_fire_probability_per_day"],
        seed=trigger_seed,
    )
    trigger_fired_fn = make_precomputed_trigger_fn(schedules)

    points = run_sweep(
        accuracy_values=accuracy_values,
        cohort=cohort,
        trigger_fired_fn=trigger_fired_fn,
        fixed_interval_days=fixed_interval_days,
        tier_fn=tier_fn,
    )

    rows = _comparison_rows(points)
    csv_path = output_dir / "adaptive_vs_fixed.csv"
    json_path = output_dir / "adaptive_vs_fixed.json"
    sweep_csv_path = output_dir / "trigger_accuracy_sweep.csv"
    _write_csv(rows, csv_path)
    _write_csv(rows, sweep_csv_path)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    outputs = {"comparison_csv": csv_path, "comparison_json": json_path, "sweep_csv": sweep_csv_path}
    for outcome in ("sans", "venous"):
        for metric in OUTCOME_METRICS:
            png_path = output_dir / f"trigger_accuracy_crossover_{outcome}_{metric}.png"
            plot_metric(points, outcome, metric, png_path)
            outputs[f"plot_{outcome}_{metric}"] = png_path
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the adaptive-vs-fixed comparison and trigger-accuracy sweep, "
        "or report structured blockers if required assumptions are unapproved."
    )
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/evaluation"))
    parser.add_argument(
        "--trigger-seed", type=int, default=0, help="Seed for the trigger-firing simulation's own randomness."
    )
    args = parser.parse_args()

    outputs = run_evaluation(
        args.observations, args.ground_truth, args.output_dir, trigger_seed=args.trigger_seed
    )

    if "blockers" in outputs:
        print(
            "Evaluation BLOCKED - either required assumptions/decisions are not "
            "approved, or the ground truth on hand is not scientifically usable for "
            "these metrics (see the blocker report for exactly which)."
        )
        print(f"  blocker report: {outputs['blockers']}")
        if "readiness_summary" in outputs:
            print(f"  ground-truth readiness summary: {outputs['readiness_summary']}")
        return 0

    print("Adaptive-vs-fixed evaluation complete.")
    for name, path in outputs.items():
        print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
