"""Export only sanitized, conspicuously labeled acceptance examples.

No hidden condition labels in profile IDs, no comparison metrics, no ground truth.
The production publisher explicitly rejects these engineering observations.
"""
import argparse
import json
from pathlib import Path

from contracts.models import SCHEMA_VERSION, AstronautDayObservation, SimulationManifest
from monitoring.engine import AssessmentResult
from research_v1.authorization import SPEC, SPEC_SHA256, authorize
from research_v1.physiology import make_case
from research_v1.run import run_case


def export_fixture(target: Path):
    authorize(engineering_fixture=True)
    observations, assessments = [], []
    for index, scenario in enumerate(("healthy", "sans", "venous", "both", "both"), 1):
        case = make_case(f"E{index}", 42, scenario)
        # Explicit acceptance input participates in the same causal loop, so
        # subsequent scheduling actually sees and follows its Urgent tier.
        history, results, _ = run_case(case, "adaptive_replacement", explicit_red_flag_days=(1,) if index == 5 else ())
        observations.extend(history)
        assessments.extend(results)
    target.mkdir(parents=True, exist_ok=True)
    # Parse through the exact public contract before writing anything.
    for o in observations:
        AstronautDayObservation.model_validate_json(o.model_dump_json())
    for r in assessments:
        AssessmentResult.model_validate_json(r.model_dump_json())
    for name, rows in (("crew_observations", observations), ("crew_scored", assessments)):
        (target / f"{name}.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8")
    manifest = SimulationManifest(run_id="engineering-42", created_at="2026-11-13T00:00:00+05:00", random_seed=42,
        crew_size=5, mission_duration_days=30, scenario_counts={}, schema_version=SCHEMA_VERSION,
        parameter_registry_parameter_count=28, assumption_registry_assumption_count=14,
        physiological_values_generated=False, generation_status="engineering_fixture_pending_approval",
        physiological_generation_blocked_reasons={"research_v1": "User-relayed model pending independent written confirmation"})
    public_manifest = manifest.model_dump()
    public_manifest.pop("scenario_counts")
    (target / "simulation_manifest.json").write_text(json.dumps(public_manifest, indent=2), encoding="utf-8")
    (target / "evaluation_blockers.json").write_text(json.dumps({"run_id": "engineering-42", "stage": "engineering_acceptance",
        "blockers": [{"capability": "research_v1_written_confirmation", "blocked_by": [],
                      "message": f"{SPEC['label']}. Confirm specification {SPEC['version']} SHA256 {SPEC_SHA256}, including all unresolved interpretations in backend/research_v1/spec.json. These outputs verify engineering behavior only."}]}, indent=2), encoding="utf-8")
    return {"profiles": 5, "observations": len(observations), "label": SPEC["label"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", required=True, type=Path)
    print(export_fixture(parser.parse_args().public_dir))
