"""Generate candidate observations privately, then acquire only fixed-policy scans.

This is an explicitly incomplete fixed-schedule demonstration, never an adaptive
experiment. Retry dates stay unassigned while approval is absent. Ground truth
and unused candidate scans stay exclusively under backend/outputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from contracts.models import AstronautDayObservation
from registry.loader import load_all
from score_crew import score_crew
from simulation.generator import generate_crew
from simulation.physiological_generation import generate_onsd_baseline


def prepare(output_dir: Path, seed=42, crew_size=300):
    registry = load_all()
    interval = registry.assumptions["fixed_schedule_interval_choice"]
    if not interval.is_active():
        raise ValueError("Fixed interval is not approved")
    # The fixed convention is explicitly approved as seven days, Day 1 anchored.
    generate_crew(crew_size=crew_size, seed=seed, mission_duration_days=30,
                          output_dir=output_dir / "candidates", run_id=f"recovery-fixed-{seed}",
                          created_at="2026-11-13T00:00:00+05:00")
    source = output_dir / "candidates"
    output_dir.mkdir(parents=True, exist_ok=True)
    observations = []
    baselines = {}
    for line in (source / "crew_observations.jsonl").read_text(encoding="utf-8").splitlines():
        obs = AstronautDayObservation.model_validate_json(line)
        scheduled = (obs.day - 1) % interval.value_or_range["primary_interval_days"] == 0
        if not scheduled:
            obs.scan = None
        elif obs.scan is not None:
            if obs.astronaut_id not in baselines:
                baselines[obs.astronaut_id] = generate_onsd_baseline(obs.astronaut_id, seed, registry)
            obs.scan.onsd_baseline_mm = baselines[obs.astronaut_id]
        obs.metadata.acquisition_policy = "fixed_7_day_day1_anchor"
        obs.metadata.scheduling_reason = "fixed_anchor_scan" if scheduled else "not_scheduled"
        observations.append(obs)
    (output_dir / "crew_observations.jsonl").write_text(
        "".join(o.model_dump_json() + "\n" for o in observations), encoding="utf-8")
    for name in ("simulation_manifest.json", "simulation_blockers.json", "ground_truth.jsonl"):
        (output_dir / name).write_bytes((source / name).read_bytes())
    score_crew(output_dir / "crew_observations.jsonl", output_dir)
    # Evaluation must use full potential observations, masked independently by
    # each policy, not the fixed policy's already-acquired subset.
    return source


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--crew-size", type=int, default=300)
    args = parser.parse_args()
    source = prepare(args.output_dir, args.seed, args.crew_size)
    print(json.dumps({"candidate_dir": str(source), "acquired_dir": str(args.output_dir)}))
