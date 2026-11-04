"""ASTROSENTINEL correction (2026-11-04), Part 7: frontend schema compatibility.

handoff/frontend/schema/*.schema.json are committed snapshots of each contract
model's Pydantic JSON schema, for a frontend that validates against them directly
rather than importing this backend's Python types. A model change (e.g. adding
SimulationManifest.capability_readiness, or TierReason.PROBABILITY_THRESHOLD) that
isn't accompanied by regenerating these files leaves a `additionalProperties: false`
schema that would reject perfectly valid new output - caught here automatically
instead of relying on someone remembering to regenerate them by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

from contracts.models import AstronautDayObservation, BlockerReport, SimulationManifest
from monitoring.engine import AssessmentResult

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "handoff" / "frontend" / "schema"

MODELS = {
    "astronaut_day_observation.schema.json": AstronautDayObservation,
    "assessment_result.schema.json": AssessmentResult,
    "blocker_report.schema.json": BlockerReport,
    "simulation_manifest.schema.json": SimulationManifest,
}


def test_schema_dir_has_no_untracked_model_files():
    assert set(p.name for p in SCHEMA_DIR.glob("*.schema.json")) == set(MODELS)


def test_committed_schemas_match_the_live_models_exactly():
    mismatched = []
    for filename, model in MODELS.items():
        committed = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        live = model.model_json_schema()
        if committed != live:
            mismatched.append(filename)
    assert mismatched == [], (
        f"{mismatched} are out of sync with their live Pydantic models - "
        f"regenerate with model.model_json_schema() and commit the result"
    )


def test_ground_truth_record_deliberately_has_no_frontend_schema():
    """GroundTruthRecord is evaluation-only and must never reach the frontend -
    the absence of a schema file for it is intentional, checked here so it can
    never be "fixed" by someone adding one without realizing why it's missing."""
    assert "ground_truth_record.schema.json" not in {p.name for p in SCHEMA_DIR.glob("*.schema.json")}
