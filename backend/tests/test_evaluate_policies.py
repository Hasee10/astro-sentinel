"""Deliverable 3 integration tests: evaluate_policies.py's executable entry point."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from evaluate_policies import build_cohort, run_evaluation
from evaluation.sweep import ObservableCase, SweepCase
from simulation.generator import generate_crew

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_build_cohort_pairs_observations_with_hidden_ground_truth_separately(tmp_path):
    paths = generate_crew(crew_size=8, seed=9, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-test")
    cohort = build_cohort(paths["crew_observations"], paths["ground_truth"])
    assert len(cohort) == 8
    for case in cohort:
        assert isinstance(case, SweepCase)
        assert isinstance(case.observable, ObservableCase)
        assert case.observable.days == list(range(1, 31))
        # ground truth exists and is scenario-structural-only (onset days null while
        # generation remains blocked) - never visible to the observable side.
        assert not hasattr(case.observable, "sans_onset_day")


def test_run_evaluation_against_real_registry_is_blocked_not_fabricated(tmp_path):
    paths = generate_crew(crew_size=8, seed=10, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-test2")
    output_dir = tmp_path / "eval"
    outputs = run_evaluation(paths["crew_observations"], paths["ground_truth"], output_dir)

    assert "blockers" in outputs
    assert outputs["blockers"].exists()
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    assert report["blockers"]  # non-empty - at least one real blocker
    # None of the real result artifacts may exist for a blocked run.
    assert not (output_dir / "adaptive_vs_fixed.csv").exists()
    assert not (output_dir / "adaptive_vs_fixed.json").exists()
    assert not list(output_dir.glob("*.png"))


def test_cli_executes_and_reports_blocked(tmp_path):
    gen_paths = generate_crew(crew_size=8, seed=11, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-cli")
    result = subprocess.run(
        [
            sys.executable, "evaluate_policies.py",
            "--observations", str(gen_paths["crew_observations"]),
            "--ground-truth", str(gen_paths["ground_truth"]),
            "--output-dir", str(tmp_path / "eval_cli"),
        ],
        cwd=BACKEND_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "BLOCKED" in result.stdout
    assert (tmp_path / "eval_cli" / "evaluation_blockers.json").exists()
