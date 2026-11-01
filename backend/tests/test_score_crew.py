"""Deliverable 2 batch-runner tests: score_crew.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from contracts.models import (
    AstronautDayObservation,
    MeasurementQuality,
    ObservationMetadata,
    QualityStatus,
    ScanMeasurement,
    ScanType,
)
from monitoring.engine import AssessmentResult
from score_crew import score_crew
from simulation.generator import generate_crew

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_score_crew_runs_end_to_end_on_generator_output(tmp_path):
    gen_paths = generate_crew(crew_size=8, seed=20, mission_duration_days=30, output_dir=tmp_path, run_id="run-score-test")
    out_paths = score_crew(gen_paths["crew_observations"], tmp_path)
    summary = json.loads(out_paths["summary"].read_text(encoding="utf-8"))
    assert summary["astronauts_scored"] == 8
    assert summary["days_scored"] == 8 * 30
    assert summary["errors"] == []
    # physiological generation remains blocked, so every tier should be unresolved
    assert summary["sans_tier_distribution"] == {"unresolved": 240}
    assert summary["venous_tier_distribution"] == {"unresolved": 240}


def test_score_crew_no_look_ahead(tmp_path):
    """A red-flag event recorded on day 10 must not affect the assessment as of day 5."""
    records = []
    for day in range(1, 11):
        scan = None
        if day == 10:
            scan = ScanMeasurement(type=ScanType.ONSD, red_flag_symptom=True, quality=MeasurementQuality(status=QualityStatus.OK))
        records.append(
            AstronautDayObservation(astronaut_id="A1", day=day, scan=scan, metadata=ObservationMetadata(run_id="fixture"))
        )
    input_path = tmp_path / "obs.jsonl"
    with input_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")

    out_paths = score_crew(input_path, tmp_path)
    scored = [
        AssessmentResult.model_validate_json(line)
        for line in out_paths["scored"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    scored_by_day = {r.as_of_day: r for r in scored}
    for day in range(1, 10):
        assert scored_by_day[day].sans.tier.value == "unresolved", f"day {day} leaked the future red flag"
    assert scored_by_day[10].sans.tier.value == "urgent"


def test_cli_executes_successfully(tmp_path):
    gen_result = subprocess.run(
        [sys.executable, "generate_crew.py", "--crew-size", "8", "--seed", "21",
         "--output-dir", str(tmp_path), "--run-id", "run-cli-score"],
        cwd=BACKEND_DIR, capture_output=True, text=True,
    )
    assert gen_result.returncode == 0, gen_result.stderr

    score_result = subprocess.run(
        [sys.executable, "score_crew.py", "--input", str(tmp_path / "crew_observations.jsonl"), "--output-dir", str(tmp_path)],
        cwd=BACKEND_DIR, capture_output=True, text=True,
    )
    assert score_result.returncode == 0, score_result.stderr
    assert (tmp_path / "crew_scored.jsonl").exists()
