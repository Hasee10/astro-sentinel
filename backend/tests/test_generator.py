"""Deliverable 1 tests: synthetic crew generator (simulation/generator.py,
generate_crew.py). Covers Defect 2 (manifest honesty about physiological
generation) and Defect 8 (deterministic replay).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from contracts.models import AstronautDayObservation, GroundTruthRecord, ScanType, SimulationManifest
from registry.loader import load_all
from simulation.generator import generate_crew, physiological_generation_status

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry():
    return load_all()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_generate_crew_runs_end_to_end(tmp_path):
    paths = generate_crew(crew_size=8, seed=1, mission_duration_days=30, output_dir=tmp_path, run_id="run-test-1")
    for p in paths.values():
        assert p.exists()


def test_correct_crew_count_and_30_day_structure(tmp_path):
    paths = generate_crew(crew_size=12, seed=2, mission_duration_days=30, output_dir=tmp_path, run_id="run-test-2")
    records = _read_jsonl(paths["crew_observations"])
    astronaut_ids = {r["astronaut_id"] for r in records}
    assert len(astronaut_ids) == 12
    for astronaut_id in astronaut_ids:
        days = sorted(r["day"] for r in records if r["astronaut_id"] == astronaut_id)
        assert days == list(range(1, 31))
    assert len(records) == 12 * 30


def test_scenario_classes_are_balanced_and_in_ground_truth_only(tmp_path):
    paths = generate_crew(crew_size=8, seed=3, mission_duration_days=30, output_dir=tmp_path, run_id="run-test-3")
    gt_records = _read_jsonl(paths["ground_truth"])
    labels = [r["scenario_label"] for r in gt_records]
    assert sorted(set(labels)) == ["both", "healthy", "slow_sans", "venous_stasis"]
    assert labels.count("healthy") == 2  # 8 crew / 4 scenario classes

    obs_records = _read_jsonl(paths["crew_observations"])
    for r in obs_records:
        assert "scenario_label" not in r["metadata"]
        assert "scenario_label" not in r


def test_reproducibility_same_seed_and_run_id_byte_identical(tmp_path):
    kwargs = dict(crew_size=8, seed=42, mission_duration_days=30, run_id="run-fixed", created_at="2026-01-01T00:00:00+00:00")
    out1, out2 = tmp_path / "run1", tmp_path / "run2"
    paths1 = generate_crew(output_dir=out1, **kwargs)
    paths2 = generate_crew(output_dir=out2, **kwargs)
    for key in paths1:
        assert paths1[key].read_bytes() == paths2[key].read_bytes(), f"{key} differs across identical replay runs"


def test_different_seeds_produce_different_scenario_assignment(tmp_path):
    kwargs = dict(crew_size=8, mission_duration_days=30, run_id="run-x", created_at="2026-01-01T00:00:00+00:00")
    paths1 = generate_crew(output_dir=tmp_path / "s1", seed=1, **kwargs)
    paths2 = generate_crew(output_dir=tmp_path / "s2", seed=2, **kwargs)
    gt1 = {r["astronaut_id"]: r["scenario_label"] for r in _read_jsonl(paths1["ground_truth"])}
    gt2 = {r["astronaut_id"]: r["scenario_label"] for r in _read_jsonl(paths2["ground_truth"])}
    assert gt1 != gt2


def test_manifest_honestly_reports_blocked_physiological_generation(tmp_path, registry):
    paths = generate_crew(crew_size=8, seed=5, mission_duration_days=30, output_dir=tmp_path, run_id="run-test-5")
    manifest = SimulationManifest.model_validate_json(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest.scenario_structure_generated is True
    # Defect 2: with all 14 assumptions unapproved today, no capability may claim
    # physiological_values_generated=True regardless of generation_status wording.
    assert manifest.physiological_values_generated is False
    assert manifest.physiological_generation_blocked_reasons  # non-empty


def test_physiological_generation_status_distinguishes_approval_from_algorithm(registry):
    """An approved NUMERICAL/SCOPE assumption alone must not flip
    physiological_values_generated to True while IMPLEMENTED_GENERATION_ALGORITHMS
    has no entry for that capability. jugular_scan_values is the live example
    today: both its required assumptions are genuinely approved, but no algorithm
    exists for it - unlike personal_onsd_baseline_values, which now has both."""
    all_generated, reasons = physiological_generation_status(registry)
    assert all_generated is False  # jugular/HRV/PTT/onset-day still block full generation
    assert "no generation algorithm is implemented" in reasons["jugular_scan_values"]
    assert "personal_onsd_baseline_values" not in reasons  # this one genuinely is ready


def test_no_invented_physiological_measurements_in_observations(tmp_path):
    """ASTROSENTINEL: ONSD IS now generated (personal_onsd_baseline_values /
    onsd_scan_values are READY) - weak_signals (HRV/PTT) and any jugular/OCT/
    visual-acuity scan remain null, since nothing authorizes generating those yet."""
    registry = load_all()
    sd_config = registry.assumptions["onsd_baseline_sd_values"].value_or_range
    low, high = sd_config["clip_range_mm"]
    max_bias = sd_config["within_person_sd_mm_base"] * 6  # generous sampling tolerance
    off_axis_bias = registry.assumptions["onsd_scan_failure_rate"].value_or_range["off_axis_positive_bias_mm"][
        "operational_value_in_use"
    ]

    paths = generate_crew(crew_size=8, seed=6, mission_duration_days=30, output_dir=tmp_path, run_id="run-test-6")
    for line in paths["crew_observations"].read_text(encoding="utf-8").splitlines():
        obs = AstronautDayObservation.model_validate_json(line)
        assert obs.weak_signals is None
        assert obs.probability.sans is None
        assert obs.probability.venous is None
        assert obs.metadata.generation_blocked is True  # jugular/HRV/PTT/onset-day still block full generation

        assert obs.scan is not None
        assert obs.scan.type == ScanType.ONSD  # never jugular/oct/visual_acuity - not generated
        assert obs.scan.jugular_area_mm2 is None
        if obs.scan.onsd_mm is not None:  # None only for the air-under-dressing failure branch
            assert low - max_bias <= obs.scan.onsd_mm <= high + off_axis_bias + max_bias


def test_invalid_mission_duration_rejected(tmp_path):
    from simulation.scenarios import ScenarioConfigError

    with pytest.raises(ScenarioConfigError):
        generate_crew(crew_size=8, seed=1, mission_duration_days=10, output_dir=tmp_path)


def test_cli_executes_successfully(tmp_path):
    result = subprocess.run(
        [sys.executable, "generate_crew.py", "--crew-size", "8", "--seed", "7",
         "--output-dir", str(tmp_path), "--run-id", "run-cli-test", "--created-at", "2026-01-01T00:00:00+00:00"],
        cwd=BACKEND_DIR, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC" in result.stdout
    assert (tmp_path / "crew_observations.jsonl").exists()
