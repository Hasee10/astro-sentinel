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
from simulation.scenarios import assign_scenarios, scenario_counts, validate_scenario_config

# capability -> the assumption_id(s) in registry/data/assumptions.json that would
# unblock it, or [] when the gap is a simulation-design choice with no registry entry
GENERATIVE_CAPABILITIES: dict[str, list[str]] = {
    "personal_onsd_baseline_values": ["onsd_baseline_sd_values"],
    "daily_hrv_weak_signal": ["hrv_trigger_assumed_accuracy"],
    "daily_ptt_weak_signal": ["ptt_trigger_assumed_usefulness"],
    "onsd_scan_values": ["onsd_baseline_sd_values"],
    "jugular_scan_values": ["jugular_flow_risk_mapping"],
    "measurement_quality_failure_injection": ["onsd_scan_failure_rate"],
}

# Defect 2: an approved numeric value does NOT by itself mean a generation algorithm
# exists. This set names the capabilities for which simulation/generator.py actually
# implements a tested numerical generation method today - it is empty, because none
# does yet. When a method is implemented and tested, add its capability name here;
# until then, physiological_values_generated in the manifest stays False even for a
# capability whose backing assumption has been approved.
IMPLEMENTED_GENERATION_ALGORITHMS: frozenset[str] = frozenset()

# gaps with no corresponding registry assumption at all - a simulation-engineering
# choice (which day to place a hidden onset on) rather than a scientific parameter
UNREGISTERED_CAPABILITIES: dict[str, str] = {
    "sans_venous_onset_day_assignment": (
        "No approved convention exists for choosing which day a hidden SANS/venous "
        "onset is placed within the 30-day mission. Picking one (e.g. a fixed day, or "
        "a sampled day) requires a human-approved simulation-design rule - it is not "
        "itself a sourced scientific parameter, but assigning it without approval would "
        "silently bake in an unreviewed assumption, which this generator does not do."
    ),
}


def blocked_capabilities(registry: Registry) -> dict[str, Blocker]:
    """Which generative capabilities are currently blocked, and by what."""
    blocked: dict[str, Blocker] = {}
    for capability, assumption_ids in GENERATIVE_CAPABILITIES.items():
        inactive = [aid for aid in assumption_ids if not registry.assumptions[aid].is_active()]
        if inactive:
            blocked[capability] = Blocker(
                capability=capability,
                blocked_by=inactive,
                message=(
                    f"Requires assumption(s) {inactive} to be approved with an assigned "
                    f"value before {capability} can be generated without fabrication."
                ),
            )
    for capability, message in UNREGISTERED_CAPABILITIES.items():
        blocked[capability] = Blocker(capability=capability, blocked_by=[], message=message)
    return blocked


def physiological_generation_status(registry: Registry) -> tuple[bool, dict[str, str]]:
    """Defect 2: distinguish "assumption approved" from "algorithm implemented".

    Returns (all_generated, reasons) where reasons maps each capability that is NOT
    producing real physiological values to why - either an inactive assumption or an
    approved assumption with no implemented generation method yet.
    """
    reasons: dict[str, str] = {}
    for capability, assumption_ids in GENERATIVE_CAPABILITIES.items():
        inactive = [aid for aid in assumption_ids if not registry.assumptions[aid].is_active()]
        if inactive:
            reasons[capability] = f"blocked: assumption(s) not approved: {inactive}"
        elif capability not in IMPLEMENTED_GENERATION_ALGORITHMS:
            reasons[capability] = (
                "assumption(s) approved, but no generation algorithm is implemented in "
                "simulation/generator.py yet - approval alone does not produce numbers"
            )
    for capability, message in UNREGISTERED_CAPABILITIES.items():
        reasons[capability] = message
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
