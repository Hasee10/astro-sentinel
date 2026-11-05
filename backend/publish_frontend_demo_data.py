#!/usr/bin/env python
"""Copies ONE consistent generate/score/evaluate run's SAFE output files into
`frontend/public/data/pipeline/`, for the frontend demo to fetch at runtime.

This script is the single place that decides what crosses the line from
"backend research output" to "published over a public URL" - see Stage 4 of
the frontend/backend integration review. Two rules it enforces:

1. Never publish evaluation-only ground truth. `ground_truth.jsonl`,
   `experiment_readiness_summary.json` (carries `ground_truth_summary` status
   counts), `pilot_info.json` (carries excluded-outcome blockers verbatim),
   and `run_status.json` (pure housekeeping, not needed by the UI) are never
   copied, regardless of what else is in the source run directory.
2. `evaluation_blockers.json` IS published (the UI needs to know the
   experiment is blocked and why, at the capability level), but its `message`
   text is sanitized first: a `*_ground_truth_consistency` blocker's message
   embeds literal per-case ground-truth status counts (e.g.
   "status counts: {'confirmed_none': 5, 'event_unknown_onset': 3}") - that is
   evaluation-only data, not a "safe status/capability label", so it is
   replaced with a fixed, capability-accurate description that carries no
   cohort-specific numbers. Every OTHER blocker's message is left byte-for-
   byte unchanged - it only ever describes code/registry approval state
   (e.g. "no implemented physiological progression model"), which is already
   public information (it is exactly what registry/design_decisions.py and
   simulation/generation_models.py say in this same repository).

Usage:
    python publish_frontend_demo_data.py --run-dir outputs/frontend_demo_v2 \\
        --public-dir ../frontend/public/data/pipeline
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# Copied verbatim - already safe (observable-only data, or code/registry-state
# metadata with no per-case ground-truth content).
_SAFE_PASSTHROUGH_FILES = (
    "crew_observations.jsonl",
    "crew_scored.jsonl",
    "scoring_summary.json",
    "simulation_manifest.json",
    "simulation_blockers.json",
)

# Never copied, no matter what - see module docstring rule 1.
_NEVER_PUBLISH_FILES = (
    "ground_truth.jsonl",
    "experiment_readiness_summary.json",
    "pilot_info.json",
    "run_status.json",
)


def _sanitize_blocker_message(capability: str, message: str) -> str:
    """Strips literal ground-truth status counts from the one blocker shape
    that carries them; every other capability's message passes through
    unchanged (see module docstring rule 2)."""
    if capability.endswith("_ground_truth_consistency"):
        outcome = capability.split("_", 1)[0]
        return (
            f"{outcome} ground truth is not fully resolved for detection-delay/"
            f"missed-event/false-escalation scoring. An event flagged with "
            f"unknown onset, or no event-occurrence model at all, must never be "
            f"scored as healthy, detected, or a valid zero."
        )
    return message


def publish(run_dir: Path, public_dir: Path) -> list[str]:
    public_dir.mkdir(parents=True, exist_ok=True)
    published: list[str] = []

    for name in _SAFE_PASSTHROUGH_FILES:
        src = run_dir / name
        if not src.exists():
            continue
        shutil.copyfile(src, public_dir / name)
        published.append(name)

    blockers_path = run_dir / "evaluation_blockers.json"
    if blockers_path.exists():
        report = json.loads(blockers_path.read_text(encoding="utf-8"))
        for blocker in report.get("blockers", []):
            blocker["message"] = _sanitize_blocker_message(blocker["capability"], blocker["message"])
        (public_dir / "evaluation_blockers.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        published.append("evaluation_blockers.json (sanitized)")

    for name in _NEVER_PUBLISH_FILES:
        if (public_dir / name).exists():
            raise RuntimeError(
                f"refusing to proceed: {public_dir / name} exists and must never "
                f"be published - remove it by hand and investigate how it got there"
            )

    return published


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="A generate/score/evaluate output directory.")
    parser.add_argument("--public-dir", type=Path, required=True, help="frontend/public/data/pipeline")
    args = parser.parse_args()

    published = publish(args.run_dir, args.public_dir)
    print(f"Published {len(published)} file(s) to {args.public_dir}:")
    for name in published:
        print(f"  {name}")
    for name in _NEVER_PUBLISH_FILES:
        print(f"  (never published: {name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
