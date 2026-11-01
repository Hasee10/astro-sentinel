#!/usr/bin/env python
"""CLI entry point for Deliverable 1. See simulation/generator.py for the logic.

Example:
    python generate_crew.py --crew-size 20 --seed 42 --output-dir outputs/run1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contracts.models import SYNTHETIC_LABEL
from simulation.generator import generate_crew
from simulation.scenarios import ScenarioConfigError


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic astronaut crew mission dataset.")
    parser.add_argument("--crew-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mission-duration-days", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument(
        "--created-at",
        type=str,
        default=None,
        help="ISO-8601 timestamp override for the manifest, for deterministic replay "
        "(use with --run-id to get byte-identical output across runs).",
    )
    args = parser.parse_args()

    try:
        paths = generate_crew(
            crew_size=args.crew_size,
            seed=args.seed,
            mission_duration_days=args.mission_duration_days,
            output_dir=args.output_dir,
            run_id=args.run_id,
            created_at=args.created_at,
        )
    except ScenarioConfigError as exc:
        print(f"Scenario configuration error: {exc}", file=sys.stderr)
        return 1

    print("Synthetic crew generation complete.")
    print(f"  {SYNTHETIC_LABEL}")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
