"""Deliverable 3 integration tests: evaluate_policies.py's executable entry point."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from evaluate_policies import build_cohort, run_evaluation
from evaluation.sweep import ObservableCase, SweepCase
from registry.loader import Registry, load_all
from registry.models import ApprovalStatus
from simulation.generator import generate_crew

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _unapproved_registry() -> Registry:
    """A fixture registry with every assumption forced back to unapproved - used to
    verify the 'blocked run never fabricates output' guarantee as a general
    property, independent of today's real (now largely approved) registry state."""
    registry = load_all()
    unapproved = {
        aid: a.model_copy(update={"approval_status": ApprovalStatus.UNAPPROVED, "approved_by": None, "value_or_range": None})
        for aid, a in registry.assumptions.items()
    }
    return Registry(parameters=registry.parameters, assumptions=unapproved)


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


def test_run_evaluation_against_unapproved_fixture_is_blocked_not_fabricated(tmp_path):
    """General property, independent of today's real (now largely approved)
    registry: when the required assumptions are NOT approved, never fabricate
    output - always write a blocker report instead."""
    paths = generate_crew(crew_size=8, seed=10, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-test2")
    output_dir = tmp_path / "eval"
    outputs = run_evaluation(
        paths["crew_observations"], paths["ground_truth"], output_dir, registry=_unapproved_registry()
    )

    assert "blockers" in outputs
    assert outputs["blockers"].exists()
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    assert report["blockers"]  # non-empty - at least one real blocker
    # None of the real result artifacts may exist for a blocked run.
    assert not (output_dir / "adaptive_vs_fixed.csv").exists()
    assert not (output_dir / "adaptive_vs_fixed.json").exists()
    assert not list(output_dir.glob("*.png"))


def test_run_evaluation_against_real_registry_still_correctly_blocked(tmp_path):
    """ASTROSENTINEL correction (2026-11-04, Part 1): sweep_blockers() alone is
    empty against the real registry, but the experiment_readiness gate now ALSO
    runs - and real generated ground truth always has has_sans_event=True astronauts
    with sans_onset_day=None (onset-day assignment is still genuinely unapproved),
    so the real pipeline correctly stays blocked, for the RIGHT new reason, not the
    old approval reason. This replaces an earlier, incorrect version of this test
    that treated the old (misleading) "genuine output" as the desired behavior."""
    paths = generate_crew(crew_size=12, seed=10, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-real")
    output_dir = tmp_path / "eval"
    outputs = run_evaluation(paths["crew_observations"], paths["ground_truth"], output_dir)

    assert "blockers" in outputs
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    capabilities = {b["capability"] for b in report["blockers"]}
    assert "sans_detection_metrics" in capabilities
    assert "venous_detection_metrics" in capabilities
    assert not (output_dir / "adaptive_vs_fixed.csv").exists()
    assert not list(output_dir.glob("*.png"))

    summary = json.loads(outputs["readiness_summary"].read_text(encoding="utf-8"))
    assert summary["ground_truth_summary"]["sans"].get("event_unknown_onset", 0) > 0


def test_sans_readiness_clears_independently_once_onset_days_are_known(tmp_path):
    """Proves the readiness gate resolves per-outcome, not as one monolithic flag:
    a hand-constructed, FULLY RESOLVED fixture SANS ground truth (every case
    confirmed_none or confirmed_with_onset) clears the SANS blocker specifically -
    venous stays blocked regardless, since no venous event-occurrence model is
    approved at all (not a data-completeness problem fixture data could solve).
    Engineering fixture only - fixture-assigned onset days are not an approved rule."""
    from dataclasses import replace

    from evaluation.experiment_readiness import check_experiment_readiness

    paths = generate_crew(crew_size=12, seed=10, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-fixture")
    cohort = build_cohort(paths["crew_observations"], paths["ground_truth"])

    resolved_cohort = []
    for case in cohort:
        gt = case.ground_truth
        if gt.has_sans_event:
            gt = replace(gt, sans_onset_day=10)  # fixture-only, not an approved rule
        resolved_cohort.append(SweepCase(observable=case.observable, ground_truth=gt))

    readiness = check_experiment_readiness(resolved_cohort)
    assert not any(b.capability == "sans_detection_metrics" for b in readiness.blockers)
    assert any(b.capability == "venous_detection_metrics" for b in readiness.blockers)
    assert readiness.ready is False  # venous alone is still enough to block the whole experiment


def test_cli_executes_and_reports_blocked(tmp_path):
    """ASTROSENTINEL correction (2026-11-04): the real CLI, against the real
    registry AND real generated ground truth, correctly reports BLOCKED - not
    because approvals are missing (they're not), but because the experiment-
    readiness gate catches the unresolved onset-day/venous-event-model gaps."""
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
    assert "blocked" in result.stdout.lower()
    assert (tmp_path / "eval_cli" / "evaluation_blockers.json").exists()
    assert not (tmp_path / "eval_cli" / "adaptive_vs_fixed.csv").exists()
    assert not list((tmp_path / "eval_cli").glob("*.png"))
