#!/usr/bin/env python
"""Deliverable 2's batch runner: score every astronaut's chronological history with
assess_history(), reassessing fresh after each new day's observation becomes available.

No look-ahead: for astronaut X's assessment as of day N, only observations with
day <= N are ever passed into assess_history() - day N+1 and later are sliced off
before the call, not merely ignored inside it.

Example:
    python score_crew.py --input outputs/run1/crew_observations.jsonl --output-dir outputs/run1
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from contracts.models import AstronautDayObservation
from monitoring.engine import AssessmentResult, HistoryError, assess_history
from monitoring.measurement_quality import validate_observation_structure
from registry.loader import load_all


def _read_observations(path: Path) -> list[AstronautDayObservation]:
    observations = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                observations.append(AstronautDayObservation.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"{path}:{line_no}: invalid observation record: {exc}") from exc
    return observations


def score_crew(input_path: Path, output_dir: Path) -> dict[str, Path]:
    registry = load_all()
    observations = _read_observations(input_path)

    by_astronaut: dict[str, list[AstronautDayObservation]] = defaultdict(list)
    for obs in observations:
        by_astronaut[obs.astronaut_id].append(obs)

    output_dir.mkdir(parents=True, exist_ok=True)
    scored_path = output_dir / "crew_scored.jsonl"

    tier_counts: dict[str, dict[str, int]] = {"sans": defaultdict(int), "venous": defaultdict(int)}
    probability_counts: dict[str, int] = {"sans": 0, "venous": 0}
    astronauts_scored = 0
    days_scored = 0
    errors: list[str] = []
    structural_warnings: list[str] = []

    with scored_path.open("w", encoding="utf-8") as out:
        for astronaut_id, records in by_astronaut.items():
            records_sorted = sorted(records, key=lambda o: o.day)
            astronauts_scored += 1
            for i in range(len(records_sorted)):
                history_so_far = records_sorted[: i + 1]  # no look-ahead: only day <= current
                # Phase 7 structural validation (section 4.1) - non-fatal: a flagged
                # record is still scored, so reviewers see both the issue and the
                # resulting assessment rather than a silently skipped day.
                for issue in validate_observation_structure(records_sorted[i]):
                    structural_warnings.append(f"{astronaut_id} day {records_sorted[i].day}: {issue}")
                try:
                    result: AssessmentResult = assess_history(history_so_far, registry)
                except HistoryError as exc:
                    errors.append(f"{astronaut_id} day {records_sorted[i].day}: {exc}")
                    continue
                out.write(result.model_dump_json() + "\n")
                days_scored += 1
                tier_counts["sans"][result.sans.tier.value] += 1
                tier_counts["venous"][result.venous.tier.value] += 1
                if result.sans.probability is not None:
                    probability_counts["sans"] += 1
                if result.venous.probability is not None:
                    probability_counts["venous"] += 1

    summary = {
        "input": str(input_path),
        "astronauts_scored": astronauts_scored,
        "days_scored": days_scored,
        "errors": errors,
        "structural_warnings": structural_warnings,
        "sans_tier_distribution": dict(tier_counts["sans"]),
        "venous_tier_distribution": dict(tier_counts["venous"]),
        "sans_probability_computed_count": probability_counts["sans"],
        "venous_probability_computed_count": probability_counts["venous"],
        "note": (
            # Computed from the actual results above, not hardcoded, so this can
            # never silently go stale as approvals/algorithms change over time.
            f"SANS probability was computed for {probability_counts['sans']}/{days_scored} "
            f"scored days (always 0 today: no monitoring-layer SANS formula exists yet, "
            f"regardless of approvals - see monitoring/engine.py). Venous probability was "
            f"computed for {probability_counts['venous']}/{days_scored} scored days via the "
            f"approved Bayesian flow-class model (0 here because generated data carries no "
            f"jugular scans yet - jugular_scan_values generation remains unimplemented). "
            f"Every non-null venous probability carries probability_label='Simulation "
            f"placeholder - unvalidated'. Remaining tiers reflect only rule-based logic "
            f"(red-flag -> urgent, poor quality -> repeat) or the explicit 'unresolved' "
            f"insufficient-evidence state."
        ),
    }
    summary_path = output_dir / "scoring_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {"scored": scored_path, "summary": summary_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-score a crew_observations.jsonl file.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()

    paths = score_crew(args.input, args.output_dir)
    print("Batch scoring complete.")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
