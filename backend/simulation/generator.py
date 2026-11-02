"""Deliverable 1: the synthetic crew generator.

Every numeric generative step is gated behind a check of whether its backing
ExperimentalAssumption is active (registry.models.ExperimentalAssumption.is_active()).
None of the 14 assumptions in the registry are approved, so every gate is currently
closed - this module still runs end to end and produces schema-valid, non-fabricated
output: structurally complete records with null measurements, a precise blocker report,
and a manifest. Approving the relevant assumption(s) later requires no code change here
to start producing real numbers - only a registry edit by the human lead.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contracts.models import (
    AstronautDayObservation,
    Blocker,
    BlockerReport,
    GroundTruthRecord,
    ObservationMetadata,
    SimulationManifest,
)
from registry.loader import Registry, load_all
from simulation.generation_models import GENERATION_MODEL_SPECS, ModelReadiness, check_readiness
from simulation.scenarios import assign_scenarios, scenario_counts, validate_scenario_config

# Phase 6 (Unified Prompt 6-7): the explicit per-capability dependency declarations
# formerly hardcoded here now live in simulation/generation_models.py as
# GENERATION_MODEL_SPECS, alongside the five-state ModelReadiness interface
# (section 3.6) and the approval-ready technical spec for each (section 3.7). This
# module only decides WHICH of those specs are this generator's concern -
# "trigger_firing_simulation_model" belongs to the evaluation sweep instead (see
# evaluation/sweep.py::sweep_blockers()), not to crew generation.
_GENERATOR_CAPABILITIES: tuple[str, ...] = tuple(
    c for c in GENERATION_MODEL_SPECS if c != "trigger_firing_simulation_model"
)


def blocked_capabilities(registry: Registry) -> dict[str, Blocker]:
    """Which generative capabilities are currently blocked, and by what."""
    blocked: dict[str, Blocker] = {}
    for capability in _GENERATOR_CAPABILITIES:
        spec = GENERATION_MODEL_SPECS[capability]
        result = check_readiness(spec, registry)
        if result.state != ModelReadiness.READY:
            blocked[capability] = Blocker(
                capability=capability,
                blocked_by=list(spec.required_assumptions),
                message="; ".join(result.reasons) or f"{capability} is not ready ({result.state.value}).",
            )
    return blocked


def physiological_generation_status(registry: Registry) -> tuple[bool, dict[str, str]]:
    """Defect 2: distinguish "assumption approved" from "algorithm implemented" -
    computed via simulation.generation_models.check_readiness() for every known
    generator capability (section 3.6's explicit readiness-state interface).

    Returns (all_generated, reasons) where reasons maps each capability that is NOT
    producing real physiological values to why.
    """
    reasons: dict[str, str] = {}
    for capability in _GENERATOR_CAPABILITIES:
        spec = GENERATION_MODEL_SPECS[capability]
        result = check_readiness(spec, registry)
        if result.state != ModelReadiness.READY:
            reasons[capability] = "; ".join(result.reasons)
    return (not reasons, reasons)


def generate_crew(
    crew_size: int,
    seed: int,
    mission_duration_days: int,
    output_dir: Path,
    run_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Path]:
    """Defect 8 (reproducibility): every file this writes is already a pure function of
    (seed, crew_size, mission_duration_days, run_id, registry contents) EXCEPT the
    manifest's created_at timestamp. Passing an explicit `run_id` (already supported)
    and an explicit `created_at` (new) makes the entire output byte-for-byte
    reproducible for verification/replay - see score_crew.py's CLI --freeze-created-at
    equivalent in evaluate_policies.py and the frontend handoff's replay instructions.
    Operational metadata (the default random run_id / wall-clock created_at) is never
    removed - this only adds an opt-in override for exact replay.
    """
    validate_scenario_config(crew_size, mission_duration_days)
    registry = load_all()
    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)

    assignment = assign_scenarios(crew_size, seed)
    blockers = blocked_capabilities(registry)
    blocker_ids = sorted(blockers)

    active_assumption_ids = [a.assumption_id for a in registry.assumptions.values() if a.is_active()]

    observations_path = output_dir / "crew_observations.jsonl"
    with observations_path.open("w", encoding="utf-8") as f:
        for astronaut_id, label in assignment.items():
            for day in range(1, mission_duration_days + 1):
                record = AstronautDayObservation(
                    astronaut_id=astronaut_id,
                    day=day,
                    weak_signals=None,
                    scan=None,
                    metadata=ObservationMetadata(
                        run_id=run_id,
                        generation_blocked=True,
                        blocked_reasons=blocker_ids,
                        approved_assumptions_used=active_assumption_ids,
                    ),
                )
                f.write(record.model_dump_json() + "\n")

    ground_truth_path = output_dir / "ground_truth.jsonl"
    with ground_truth_path.open("w", encoding="utf-8") as f:
        for astronaut_id, label in assignment.items():
            record = GroundTruthRecord(
                astronaut_id=astronaut_id,
                scenario_label=label,
                sans_onset_day=None,
                venous_onset_day=None,
                run_id=run_id,
                blocked_reasons=["sans_venous_onset_day_assignment"] if label != "healthy" else [],
            )
            f.write(record.model_dump_json() + "\n")

    physio_generated, physio_reasons = physiological_generation_status(registry)
    manifest = SimulationManifest(
        run_id=run_id,
        created_at=created_at,
        random_seed=seed,
        crew_size=crew_size,
        mission_duration_days=mission_duration_days,
        scenario_counts=scenario_counts(assignment),
        parameter_registry_parameter_count=len(registry.parameters),
        assumption_registry_assumption_count=len(registry.assumptions),
        active_assumption_ids=active_assumption_ids,
        scenario_structure_generated=True,
        physiological_values_generated=physio_generated,
        physiological_generation_blocked_reasons=physio_reasons,
        generation_status="fully_blocked" if blockers else "complete",
    )
    manifest_path = output_dir / "simulation_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    blocker_report = BlockerReport(run_id=run_id, stage="generate_crew", blockers=list(blockers.values()))
    blockers_path = output_dir / "simulation_blockers.json"
    blockers_path.write_text(blocker_report.model_dump_json(indent=2), encoding="utf-8")

    return {
        "crew_observations": observations_path,
        "ground_truth": ground_truth_path,
        "manifest": manifest_path,
        "blockers": blockers_path,
    }
