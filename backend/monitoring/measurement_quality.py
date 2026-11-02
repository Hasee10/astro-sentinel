"""Phase 7 (Unified Prompt 6-7, section 4): measurement validation and quality-state
processing.

Two separate things live here, deliberately kept apart:

1. `validate_observation_structure()` - pure structural self-consistency checks
   (does this record make internal sense) with NO clinical content: field presence,
   type-appropriate fields, no mixing of unrelated scan-type fields. Everything
   Pydantic's own typed model already enforces (field types, enum membership,
   extra="forbid") is NOT repeated here - this only checks cross-field consistency
   Pydantic cannot express on its own.

2. `derive_onsd_quality()` - the ONE sourced, deterministic quality rule this
   project can defend today: on-axis acquisition is an established requirement in
   the mission document's own ONSD measurement protocol
   (`onsd_measurement_protocol`/`onsd_technical_artifacts`), so an off-axis scan is
   a documented technical artifact, not an invented threshold. This function
   NEVER invents a numeric confidence weight, error variance, or failure
   probability - see simulation/generation_models.py's
   `measurement_quality_failure_injection` spec for why randomized failure
   injection is a separate, still-blocked capability.

Neither function performs probability calculation or tier assignment - that stays
in monitoring/engine.py, which calls `derive_onsd_quality()` only to fill in a
quality status the generator/caller left unset, never to override one explicitly
recorded.
"""
from __future__ import annotations

from contracts.models import (
    AstronautDayObservation,
    MeasurementQuality,
    QualityStatus,
    ScanMeasurement,
    ScanType,
)

# Fields that only make sense for a given scan type - used to catch a record that
# mixes, say, jugular fields into a scan typed ONSD. Structural self-consistency
# only; no clinical meaning is attached to the values themselves here.
_ONSD_ONLY_FIELDS = ("onsd_mm", "on_axis", "oct_disc_edema", "visual_acuity_change")
_JUGULAR_ONLY_FIELDS = ("jugular_area_mm2", "jugular_flow_class", "jugular_collapsibility_lost")

_SCAN_TYPE_ALLOWED_FIELDS: dict[ScanType, tuple[str, ...]] = {
    ScanType.ONSD: _ONSD_ONLY_FIELDS,
    ScanType.OCT: ("oct_disc_edema",),
    ScanType.VISUAL_ACUITY: ("visual_acuity_change",),
    ScanType.JUGULAR: _JUGULAR_ONLY_FIELDS,
    ScanType.SYMPTOMS: (),  # symptoms carry only red_flag_symptom, which is universal
}

_ALL_TYPED_FIELDS = _ONSD_ONLY_FIELDS + _JUGULAR_ONLY_FIELDS


def validate_observation_structure(obs: AstronautDayObservation) -> list[str]:
    """Structural self-consistency errors for one observation record, or [] if
    clean. Never raises - the caller (score_crew.py) decides how to report these."""
    errors: list[str] = []

    if not obs.astronaut_id or not obs.astronaut_id.strip():
        errors.append("astronaut_id is empty")
    if obs.day < 1:
        errors.append(f"day must be >= 1, got {obs.day}")

    scan = obs.scan
    if scan is None:
        return errors

    if scan.quality is None:
        errors.append("scan is present but has no quality metadata")

    if scan.type is None:
        if any(getattr(scan, f) is not None for f in _ALL_TYPED_FIELDS):
            errors.append("scan has type-specific fields set but no scan.type declared")
        return errors

    allowed = set(_SCAN_TYPE_ALLOWED_FIELDS.get(scan.type, ()))
    disallowed_fields = [f for f in _ALL_TYPED_FIELDS if f not in allowed and getattr(scan, f) is not None]
    if disallowed_fields:
        errors.append(f"scan.type={scan.type.value} but unrelated field(s) set: {disallowed_fields}")

    if scan.quality is not None and scan.quality.status == QualityStatus.NOT_TAKEN:
        set_values = [f for f in _ALL_TYPED_FIELDS if getattr(scan, f) is not None]
        if set_values:
            errors.append(f"quality.status is NOT_TAKEN but measurement value(s) are set: {set_values}")

    return errors


def derive_onsd_quality(scan: ScanMeasurement) -> MeasurementQuality:
    """The one sourced, deterministic ONSD quality rule (section 4.2): on-axis
    acquisition is a documented protocol requirement
    (`onsd_measurement_protocol`); its absence is a named technical artifact
    (`onsd_technical_artifacts`), not an invented cutoff.

    - `scan.quality` already set -> returned unchanged (an explicit quality call,
      e.g. from a future failure-injection model, is never silently overridden).
    - `scan.on_axis is False` -> DEGRADED (documented technical artifact).
    - `scan.on_axis is None` -> UNKNOWN ("quality cannot be established" - the
      protocol's own acquisition-geometry requirement was never recorded).
    - `scan.on_axis is True` -> OK.

    Deliberately does NOT invent a numeric confidence weight or error variance -
    `MeasurementQuality.weight` is left at its contract default (1.0) rather than
    being set from an unsourced formula.
    """
    if scan.quality is not None:
        return scan.quality
    if scan.on_axis is False:
        return MeasurementQuality(
            status=QualityStatus.DEGRADED,
            reasons=["off-axis acquisition (onsd_technical_artifacts: documented technical artifact)"],
        )
    if scan.on_axis is None:
        return MeasurementQuality(
            status=QualityStatus.UNKNOWN,
            reasons=["on-axis acquisition metadata (onsd_measurement_protocol) was not recorded"],
        )
    return MeasurementQuality(status=QualityStatus.OK)
