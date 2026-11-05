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
    """ASTROSENTINEL correction (2026-11-04, Part 1 + same-day extension):
    sweep_blockers() alone is empty against the real registry, but the
    experiment_readiness gate now ALSO runs. Real generated ground truth always
    has has_sans_event=True astronauts with sans_onset_day=None (onset-day
    assignment is still genuinely unapproved) - AND, independently, no
    physiological progression model or SANS monitoring rule exists yet, and
    venous is missing all three of its eligibility conditions. The real pipeline
    correctly stays blocked, for ALL of these reasons at once, none of them
    papered over by the others."""
    paths = generate_crew(crew_size=12, seed=10, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-real")
    output_dir = tmp_path / "eval"
    outputs = run_evaluation(paths["crew_observations"], paths["ground_truth"], output_dir)

    assert "blockers" in outputs
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    capabilities = {b["capability"] for b in report["blockers"]}
    assert "sans_ground_truth_consistency" in capabilities
    assert "sans_physiological_progression" in capabilities
    assert "sans_monitoring_rule" in capabilities
    assert "venous_ground_truth_consistency" in capabilities
    assert "venous_physiological_progression" in capabilities
    assert "venous_eligibility_conditions" in capabilities
    assert not (output_dir / "adaptive_vs_fixed.csv").exists()
    assert not (output_dir / "pilot_info.json").exists()
    assert not list(output_dir.glob("*.png"))

    summary = json.loads(outputs["readiness_summary"].read_text(encoding="utf-8"))
    assert summary["ground_truth_summary"]["sans"].get("event_unknown_onset", 0) > 0


def test_sans_readiness_clears_independently_once_onset_days_are_known(tmp_path):
    """Proves the readiness gate resolves per-outcome AND per-check, not as one
    monolithic flag: a hand-constructed, FULLY RESOLVED fixture SANS ground truth
    (every case confirmed_none or confirmed_with_onset) clears the SANS
    ground-truth-consistency blocker specifically. This is the explicit
    "resolving onset timing alone cannot produce an apparently valid full
    experiment" regression (ASTROSENTINEL correction, same-day extension):
    sans_physiological_progression and sans_monitoring_rule are INDEPENDENT
    capabilities that resolving onset timing says nothing about, so SANS still
    blocks overall - and venous stays blocked regardless, since no venous
    event-occurrence model is approved at all (not a data-completeness problem
    fixture data could solve). Engineering fixture only - fixture-assigned onset
    days are not an approved rule."""
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

    readiness = check_experiment_readiness(resolved_cohort, load_all())
    capabilities = {b.capability for b in readiness.blockers}
    assert "sans_ground_truth_consistency" not in capabilities  # onset timing: fully resolved
    assert "sans_physiological_progression" in capabilities  # WHAT HAPPENS: still blocked
    assert "sans_monitoring_rule" in capabilities  # detection formula: still blocked
    assert "venous_ground_truth_consistency" in capabilities
    assert readiness.ready is False  # resolving onset timing alone never makes the experiment ready


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


def test_use_adaptive_replacement_flag_reaches_the_real_gate(tmp_path):
    """Confirms run_evaluation's new use_adaptive_replacement parameter actually
    reaches check_experiment_readiness - against the real (unapproved) design
    decision this still blocks, now also naming adaptive_replacement_scheduling
    alongside the other real blockers, never silently ignored."""
    paths = generate_crew(crew_size=8, seed=12, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-adaptive")
    output_dir = tmp_path / "eval"
    outputs = run_evaluation(
        paths["crew_observations"], paths["ground_truth"], output_dir, use_adaptive_replacement=True
    )
    assert "blockers" in outputs
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    capabilities = {b["capability"] for b in report["blockers"]}
    assert "adaptive_replacement_scheduling" in capabilities


def _patched_for_sans_only_pilot(monkeypatch):
    """Shared setup: simulates SANS's progression + monitoring-rule capabilities
    being ready (not approved/implemented for real today) so pilot mode can be
    exercised end-to-end without waiting on those approvals."""
    from dataclasses import replace

    import evaluation.experiment_readiness as er_module
    import monitoring.engine as engine_module
    import simulation.generation_models as gm_module
    from registry.design_decisions import DesignDecision

    approved_progression_decision = DesignDecision(
        decision_id="sans_physiological_progression",
        description="test",
        approved=True,
        decision_text="Linear ramp over 5 days to a fixed target magnitude.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "sans_physiological_progression", approved_progression_decision)
    monkeypatch.setitem(
        gm_module.GENERATION_MODEL_SPECS,
        "sans_physiological_progression",
        replace(gm_module.GENERATION_MODEL_SPECS["sans_physiological_progression"], has_implemented_rule=True),
    )
    monkeypatch.setattr(engine_module, "MONITORING_PROBABILITY_IMPLEMENTED", {"sans", "venous"})


def _resolve_sans_onset_ground_truth(ground_truth_path: Path, resolved_path: Path) -> None:
    """Writes a copy of `ground_truth_path` with every SANS-event case's onset
    day resolved (fixture-only, not an approved rule) - model_copy preserves
    every other required field (scenario_label, run_id, ...)."""
    from contracts.models import GroundTruthRecord

    resolved_lines = []
    with ground_truth_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = GroundTruthRecord.model_validate_json(line)
            if record.has_sans_event:
                record = record.model_copy(update={"sans_onset_day": 10})
            resolved_lines.append(record.model_dump_json())
    resolved_path.write_text("\n".join(resolved_lines) + "\n", encoding="utf-8")


def test_pilot_run_writes_sans_only_output_and_labels_it(tmp_path, monkeypatch):
    """End-to-end wiring test for Part 6: once SANS independently clears (here
    simulated) and allow_sans_only_pilot=True is explicitly passed, run_evaluation
    must write SANS-only CSV/JSON/PNG output, a pilot_info.json naming exactly
    which outcome was excluded and why, and never write a venous row or PNG -
    the full two-outcome study must never be presented as complete."""
    _patched_for_sans_only_pilot(monkeypatch)

    paths = generate_crew(crew_size=8, seed=13, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-pilot")
    ground_truth_path = tmp_path / "resolved_ground_truth.jsonl"
    _resolve_sans_onset_ground_truth(paths["ground_truth"], ground_truth_path)

    output_dir = tmp_path / "eval_pilot"
    outputs = run_evaluation(
        paths["crew_observations"], ground_truth_path, output_dir, allow_sans_only_pilot=True
    )

    assert "blockers" not in outputs
    assert "pilot_info" in outputs
    pilot_info = json.loads(outputs["pilot_info"].read_text(encoding="utf-8"))
    assert pilot_info["included_outcomes"] == ["sans"]
    assert pilot_info["excluded_outcomes"] == ["venous"]
    assert pilot_info["excluded_outcome_blockers"]  # kept, not dropped

    rows = json.loads(outputs["comparison_json"].read_text(encoding="utf-8"))
    assert rows  # real output was written
    assert all(row["outcome"] == "sans" for row in rows)

    assert any("plot_sans_" in name for name in outputs)
    assert not any("plot_venous_" in name for name in outputs)
    assert not list(output_dir.glob("*venous*.png"))


def test_pilot_mode_off_by_default_even_with_sans_cleared(tmp_path, monkeypatch):
    """The same cleared-SANS simulation as above, but WITHOUT
    allow_sans_only_pilot - must stay fully blocked (never silently default into
    a partial result just because SANS happens to be ready)."""
    _patched_for_sans_only_pilot(monkeypatch)

    paths = generate_crew(crew_size=8, seed=14, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-nopilot")
    output_dir = tmp_path / "eval_nopilot"
    outputs = run_evaluation(paths["crew_observations"], paths["ground_truth"], output_dir)

    assert "blockers" in outputs
    assert not (output_dir / "adaptive_vs_fixed.csv").exists()


def test_pilot_mode_blocked_end_to_end_by_an_unapproved_adaptive_replacement_request(tmp_path, monkeypatch):
    """Round-3 regression ('fix pilot-mode authorization bypass'), exercised
    through the real run_evaluation() entry point rather than
    check_experiment_readiness() directly: SANS cleared, onset timing resolved,
    allow_sans_only_pilot=True AND use_adaptive_replacement=True (unapproved) in
    the SAME call. The pilot must NOT activate and NO result output may be
    written - the adaptive-replacement blocker is global-scope and must never
    be excluded just because SANS itself is clean."""
    _patched_for_sans_only_pilot(monkeypatch)

    paths = generate_crew(crew_size=8, seed=15, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-pilot-global")
    ground_truth_path = tmp_path / "resolved_ground_truth.jsonl"
    _resolve_sans_onset_ground_truth(paths["ground_truth"], ground_truth_path)

    output_dir = tmp_path / "eval_pilot_global"
    outputs = run_evaluation(
        paths["crew_observations"],
        ground_truth_path,
        output_dir,
        allow_sans_only_pilot=True,
        use_adaptive_replacement=True,
    )

    assert "blockers" in outputs
    assert "pilot_info" not in outputs
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    capabilities = {b["capability"] for b in report["blockers"]}
    assert "adaptive_replacement_scheduling" in capabilities
    assert not (output_dir / "adaptive_vs_fixed.csv").exists()
    assert not (output_dir / "pilot_info.json").exists()
    assert not list(output_dir.glob("*.png"))


def test_adaptive_replacement_approved_decision_alone_still_blocks_the_real_run(tmp_path, monkeypatch):
    """Round-3 regression ('do not merely flip an approval boolean'), exercised
    through run_evaluation(): approving adaptive_scheduling_policy_semantics
    alone (execution wiring still false, the real state today) must still
    block a use_adaptive_replacement=True request - approval alone would not
    change what evaluation.sweep.run_sweep() actually executes."""
    import evaluation.experiment_readiness as er_module
    import evaluation.sweep as sweep_module
    from registry.design_decisions import DesignDecision

    approved_decision = DesignDecision(
        decision_id="adaptive_scheduling_policy_semantics",
        description="test",
        approved=True,
        decision_text="Option B, max_gap_days=5, defer_lookback_days=3.",
        approved_by="Research Lead",
    )
    monkeypatch.setitem(er_module.DESIGN_DECISIONS, "adaptive_scheduling_policy_semantics", approved_decision)
    monkeypatch.setattr(sweep_module, "ADAPTIVE_REPLACEMENT_EXECUTION_WIRED", False)

    paths = generate_crew(crew_size=8, seed=16, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-adaptive2")
    output_dir = tmp_path / "eval_adaptive2"
    outputs = run_evaluation(
        paths["crew_observations"], paths["ground_truth"], output_dir, use_adaptive_replacement=True
    )

    assert "blockers" in outputs
    report = json.loads(outputs["blockers"].read_text(encoding="utf-8"))
    capabilities = {b["capability"] for b in report["blockers"]}
    assert "adaptive_replacement_scheduling" in capabilities


# ---- blocked-run output safety: stale results must never masquerade as current ----


def test_blocked_rerun_flags_stale_results_from_a_prior_successful_run_without_deleting_them(tmp_path, monkeypatch):
    """Point 4 ('blocked run output safety'): a successful (pilot) run into
    --output-dir X, followed by a blocked rerun into the SAME directory X, must
    never let the first run's CSV/PNG be mistaken for the second (blocked)
    run's result. The files are left alone (no destructive removal without
    explicit authorization) but run_status.json must flag them as stale and
    name the real outcome of the run that just happened."""
    _patched_for_sans_only_pilot(monkeypatch)
    paths = generate_crew(crew_size=8, seed=17, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-stale")
    ground_truth_path = tmp_path / "resolved_ground_truth.jsonl"
    _resolve_sans_onset_ground_truth(paths["ground_truth"], ground_truth_path)
    output_dir = tmp_path / "eval_stale"

    first = run_evaluation(paths["crew_observations"], ground_truth_path, output_dir, allow_sans_only_pilot=True)
    assert "pilot_info" in first
    assert (output_dir / "adaptive_vs_fixed.csv").exists()
    sans_png_names = [name for name in first if name.startswith("plot_sans_")]
    assert sans_png_names
    first_png_path = first[sans_png_names[0]]
    assert first_png_path.exists()

    # Rerun into the SAME output_dir, now with the ORIGINAL (unresolved) ground
    # truth - the SANS-clearing monkeypatches from _patched_for_sans_only_pilot
    # are still active (monkeypatch only undoes them after this test function
    # returns), but that alone is not enough: sans_ground_truth_consistency
    # fires again on the unresolved onset days, and venous stays blocked
    # regardless - so this second run is genuinely, correctly blocked.
    second = run_evaluation(paths["crew_observations"], paths["ground_truth"], output_dir)

    assert "blockers" in second
    # The prior run's files must still physically exist - never auto-deleted.
    assert (output_dir / "adaptive_vs_fixed.csv").exists()
    assert first_png_path.exists()

    status = json.loads(second["run_status"].read_text(encoding="utf-8"))
    assert status["status"] == "blocked"
    assert "adaptive_vs_fixed.csv" in status["stale_result_files_from_a_prior_run"]
    assert first_png_path.name in status["stale_result_files_from_a_prior_run"]
    assert "adaptive_vs_fixed.csv" not in status["files_written_this_run"]


def test_run_status_on_a_successful_run_lists_only_its_own_files_as_written(tmp_path, monkeypatch):
    """The companion case: a clean --output-dir with no prior run at all must
    report an empty stale-files list, and files_written_this_run must name
    exactly the real output this run produced."""
    _patched_for_sans_only_pilot(monkeypatch)
    paths = generate_crew(crew_size=8, seed=18, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-freshstatus")
    ground_truth_path = tmp_path / "resolved_ground_truth.jsonl"
    _resolve_sans_onset_ground_truth(paths["ground_truth"], ground_truth_path)
    output_dir = tmp_path / "eval_freshstatus"

    outputs = run_evaluation(paths["crew_observations"], ground_truth_path, output_dir, allow_sans_only_pilot=True)
    status = json.loads(outputs["run_status"].read_text(encoding="utf-8"))

    assert status["status"] == "pilot"
    assert status["stale_result_files_from_a_prior_run"] == []
    assert "adaptive_vs_fixed.csv" in status["files_written_this_run"]
    assert "run_status.json" not in status["files_written_this_run"]


def test_blocked_run_writes_run_status_with_no_prior_output(tmp_path):
    """A blocked run against a clean directory must still write run_status.json,
    correctly reporting no stale files (there is nothing to be stale yet)."""
    paths = generate_crew(crew_size=8, seed=19, mission_duration_days=30, output_dir=tmp_path, run_id="run-eval-cleanblocked")
    output_dir = tmp_path / "eval_cleanblocked"
    outputs = run_evaluation(paths["crew_observations"], paths["ground_truth"], output_dir)

    assert "run_status" in outputs
    status = json.loads(outputs["run_status"].read_text(encoding="utf-8"))
    assert status["status"] == "blocked"
    assert status["stale_result_files_from_a_prior_run"] == []
