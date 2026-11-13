"""The shared data contract all three deliverables read and write.

One record per astronaut per day, extending the mission brief's illustrative sketch
with independent sans/venous probability and tier objects (never a combined score -
see [[nasa-fluid-shift-scientific-constraints]] / Correction 1 from Phase 0 review).

Every numeric field is Optional and defaults to None. None means "no value" - it is
never replaced with 0, an invented default, or a placeholder number.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.7.0"
SYNTHETIC_LABEL = "SYNTHETIC - NOT REAL ASTRONAUT DATA"


class ScenarioLabel(str, Enum):
    HEALTHY = "healthy"
    SLOW_SANS = "slow_sans"
    VENOUS_STASIS = "venous_stasis"
    BOTH = "both"


class ScanType(str, Enum):
    ONSD = "onsd"
    JUGULAR = "jugular"
    OCT = "oct"
    VISUAL_ACUITY = "visual_acuity"
    SYMPTOMS = "symptoms"


class QualityStatus(str, Enum):
    """Schema v0.3.0 adds UNKNOWN (additive, non-breaking - OK/DEGRADED/FAILED/
    NOT_TAKEN are unchanged): a scan whose documented protocol metadata (e.g.
    on-axis acquisition) was never recorded, so quality cannot be established
    either way - distinct from NOT_TAKEN (no scan attempted at all). See
    monitoring/measurement_quality.py for the one sourced rule that can derive
    this automatically."""

    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_TAKEN = "not_taken"
    UNKNOWN = "unknown"


class TierValue(str, Enum):
    MONITOR = "monitor"
    REPEAT = "repeat"
    CONSULT = "consult"
    URGENT = "urgent"
    UNRESOLVED = "unresolved"  # explicit insufficient-evidence state, never a guess


class TierReason(str, Enum):
    """Schema v0.4.0 (additive): WHY a tier was assigned, kept structurally
    separate from the tier itself (section 4, Unified Prompt 8-9) - a
    measurement-quality Repeat is not evidence a physiological event was
    detected, and must never be read as one just because the tier is Repeat."""

    RED_FLAG_SYMPTOM = "red_flag_symptom"
    MEASUREMENT_QUALITY = "measurement_quality"
    INSUFFICIENT_EVIDENCE_FOR_PROBABILITY = "insufficient_evidence_for_probability"
    # Schema v0.5.0 (additive, ASTROSENTINEL): a tier derived from an actual computed
    # probability against decision_tier_thresholds - always paired with
    # OutcomeAssessment.probability_label to keep "hypothetical simulation estimate"
    # visibly attached, never presented as a validated clinical tier.
    PROBABILITY_THRESHOLD = "probability_threshold"
    PERSISTENT_SERIOUS_EVIDENCE = "persistent_serious_evidence"


class WeakSignals(BaseModel):
    """Daily cheap signals. Units: hrv_hf_power/hrv_lf_hf are dimensionless ratios as
    given in the source (no further normalization is specified); ptt_ms is milliseconds."""

    model_config = ConfigDict(extra="forbid")

    hrv_hf_power: Optional[float] = None
    hrv_lf_hf: Optional[float] = None
    ptt_ms: Optional[float] = None


class MeasurementQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: QualityStatus
    reasons: list[str] = Field(default_factory=list)
    weight: float = 1.0  # how much this scan may move an estimate; ~0 if failed


class ScanMeasurement(BaseModel):
    """Structured confirmatory measurement. Units: onsd_mm, jugular_area_mm2 as named."""

    model_config = ConfigDict(extra="forbid")

    type: Optional[ScanType] = None
    onsd_mm: Optional[float] = None
    onsd_baseline_mm: Optional[float] = None
    on_axis: Optional[bool] = None  # acquisition geometry; feeds quality check
    jugular_area_mm2: Optional[float] = None
    jugular_baseline_mm2: Optional[float] = None
    jugular_flow_class: Optional[str] = None  # antegrade / stagnant / retrograde
    jugular_collapsibility_lost: Optional[bool] = None
    oct_disc_edema: Optional[bool] = None
    visual_acuity_change: Optional[str] = None
    red_flag_symptom: Optional[bool] = None
    quality: Optional[MeasurementQuality] = None


class ScanSession(BaseModel):
    """One acquisition session, with independent outcome-specific measurements."""
    model_config = ConfigDict(extra="forbid")
    session_id: str
    policy: str
    reason_codes: list[str]
    is_retry: bool = False
    measurements: list[ScanMeasurement]

    @model_validator(mode="after")
    def validate_measurements(self):
        types = [m.type for m in self.measurements]
        if sorted(t.value if t else "" for t in types) != ["jugular", "onsd"]:
            raise ValueError("A shared session must attempt one ONSD and one jugular measurement")
        return self


class OutcomeProbability(BaseModel):
    """SANS and venous probabilities are always independent fields - never a
    combined/overall score. None means no validated calculation is currently possible;
    0 is never substituted for an unknown probability."""

    model_config = ConfigDict(extra="forbid")

    sans: Optional[float] = None
    venous: Optional[float] = None


class OutcomeTier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sans: Optional[TierValue] = None
    venous: Optional[TierValue] = None


class ObservationMetadata(BaseModel):
    """Monitoring-visible provenance only. Schema v0.2.0 introduced a breaking change from v0.1.0:
    ``scenario_label`` was REMOVED from here - see Defect 1 of the Unified Prompt 4-5
    corrective review. A hidden ground-truth scenario identity must never be readable
    from a record that the monitoring engine, scheduler, or frontend can see. Scenario
    label and onset-day information now live exclusively on GroundTruthRecord, which
    is written to a separate evaluation-only file and is never passed to
    assess_history() or any scheduling policy."""

    model_config = ConfigDict(extra="forbid")

    synthetic: bool = True
    synthetic_label: str = SYNTHETIC_LABEL
    run_id: str
    acquisition_policy: Optional[str] = None
    scheduling_reason: Optional[str] = None
    observable_triggers: dict[str, bool] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    generation_blocked: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    approved_assumptions_used: list[str] = Field(default_factory=list)


class AstronautDayObservation(BaseModel):
    """One record per astronaut per day - the shared contract's core unit."""

    model_config = ConfigDict(extra="forbid")

    astronaut_id: str
    day: int
    weak_signals: Optional[WeakSignals] = None
    scan: Optional[ScanMeasurement] = None
    scan_session: Optional[ScanSession] = None
    probability: OutcomeProbability = Field(default_factory=OutcomeProbability)
    tier: OutcomeTier = Field(default_factory=OutcomeTier)
    metadata: ObservationMetadata

    @model_validator(mode="after")
    def validate_acquisition(self):
        if self.scan is not None and self.scan_session is not None:
            raise ValueError("Use legacy scan OR shared scan_session, never both")
        return self


def measurements_of(observation: AstronautDayObservation) -> list[ScanMeasurement]:
    if observation.scan_session is not None:
        return observation.scan_session.measurements
    return [observation.scan] if observation.scan is not None else []


class GroundTruthRecord(BaseModel):
    """Hidden evaluation-only label. The monitoring pipeline must never read this.

    Schema v0.5.0 (additive, ASTROSENTINEL): adds the SANS synthetic susceptibility
    profile now that sans_prior_mapping is approved. `is_sans_high_susceptibility`
    and `has_sans_event` are ground-truth bookkeeping for the GENERATOR only - neither
    is, or ever becomes, assess_history()'s probability.sans output, which stays null
    (see sans_prior_mapping's note: the event-onset day and progression curve remain
    separately unapproved). `synthetic_sans_prior_label` is carried alongside as a
    constant reminder of that distinction wherever this record is inspected.
    """

    model_config = ConfigDict(extra="forbid")

    astronaut_id: str
    scenario_label: ScenarioLabel
    sans_onset_day: Optional[int] = None
    venous_onset_day: Optional[int] = None
    run_id: str
    blocked_reasons: list[str] = Field(default_factory=list)
    is_sans_high_susceptibility: Optional[bool] = None
    has_sans_event: Optional[bool] = None
    synthetic_sans_prior_label: Optional[str] = None


class Blocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    blocked_by: list[str] = Field(default_factory=list)  # assumption_id(s)
    message: str


class BlockerReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage: str
    blockers: list[Blocker] = Field(default_factory=list)


class SimulationManifest(BaseModel):
    """Defect 2 fix: an approved numeric assumption authorizes a VALUE, not a working
    GENERATION ALGORITHM for that value - the two fields below must never be collapsed
    into one "generation_status" string, because that previously let "complete"-looking
    status imply a physiological model that does not yet exist in code."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: str
    random_seed: int
    crew_size: int
    mission_duration_days: int
    scenario_counts: dict[str, int]
    schema_version: str = SCHEMA_VERSION
    parameter_registry_parameter_count: int
    assumption_registry_assumption_count: int
    active_assumption_ids: list[str] = Field(default_factory=list)

    # Always True once this manifest exists: assigning astronauts to scenario classes
    # and laying out the 30-day record skeleton requires no blocked scientific input.
    scenario_structure_generated: bool = True

    # True only if every GENERATIVE_CAPABILITIES gate was both (a) approved in the
    # registry AND (b) backed by an implemented, tested generation algorithm in
    # simulation/generator.py. Approving an assumption value alone does not flip this.
    physiological_values_generated: bool = False

    # Capability name -> why physiological values are unavailable for it right now.
    # Empty only when physiological_values_generated is True.
    physiological_generation_blocked_reasons: dict[str, str] = Field(default_factory=dict)

    # ASTROSENTINEL correction (2026-11-04): generation_status below was a binary
    # "fully_blocked"/"complete" string in practice despite this docstring already
    # naming "partially_blocked" as a valid value - a real reporting defect, since
    # 3/7 generator capabilities were genuinely READY while the whole run still read
    # "fully_blocked". Fixed to actually use all three states, and this field adds
    # the full per-capability picture (one of simulation.generation_models.ModelReadiness's
    # five values each) so "partially_blocked" is never the only signal available.
    capability_readiness: dict[str, str] = Field(default_factory=dict)

    generation_status: str  # "fully_blocked" | "partially_blocked" | "complete"
