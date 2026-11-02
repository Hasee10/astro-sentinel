"""Phase 7 tests: monitoring/measurement_quality.py."""
from __future__ import annotations

from contracts.models import (
    AstronautDayObservation,
    MeasurementQuality,
    ObservationMetadata,
    QualityStatus,
    ScanMeasurement,
    ScanType,
)
from monitoring.measurement_quality import derive_onsd_quality, validate_observation_structure


def _obs(day=1, scan=None):
    return AstronautDayObservation(astronaut_id="A1", day=day, scan=scan, metadata=ObservationMetadata(run_id="fixture"))


# ---- derive_onsd_quality ----


def test_on_axis_true_is_ok():
    scan = ScanMeasurement(type=ScanType.ONSD, on_axis=True)
    assert derive_onsd_quality(scan).status == QualityStatus.OK


def test_off_axis_is_degraded_with_documented_reason():
    scan = ScanMeasurement(type=ScanType.ONSD, on_axis=False)
    quality = derive_onsd_quality(scan)
    assert quality.status == QualityStatus.DEGRADED
    assert "off-axis" in quality.reasons[0]


def test_unrecorded_on_axis_is_unknown_not_a_guess():
    scan = ScanMeasurement(type=ScanType.ONSD, on_axis=None)
    quality = derive_onsd_quality(scan)
    assert quality.status == QualityStatus.UNKNOWN


def test_explicit_quality_is_never_overridden():
    explicit = MeasurementQuality(status=QualityStatus.FAILED, reasons=["sensor fault"])
    scan = ScanMeasurement(type=ScanType.ONSD, on_axis=True, quality=explicit)
    assert derive_onsd_quality(scan) is explicit


def test_never_assigns_a_numeric_confidence_weight():
    scan = ScanMeasurement(type=ScanType.ONSD, on_axis=False)
    quality = derive_onsd_quality(scan)
    assert quality.weight == 1.0  # contract default, never set from an unsourced formula


# ---- validate_observation_structure ----


def test_clean_observation_has_no_errors():
    scan = ScanMeasurement(type=ScanType.ONSD, onsd_mm=5.0, quality=MeasurementQuality(status=QualityStatus.OK))
    assert validate_observation_structure(_obs(scan=scan)) == []


def test_observation_with_no_scan_has_no_errors():
    assert validate_observation_structure(_obs()) == []


def test_empty_astronaut_id_flagged():
    obs = AstronautDayObservation(astronaut_id="  ", day=1, metadata=ObservationMetadata(run_id="fixture"))
    errors = validate_observation_structure(obs)
    assert any("astronaut_id" in e for e in errors)


def test_scan_without_quality_metadata_flagged():
    scan = ScanMeasurement(type=ScanType.ONSD, onsd_mm=5.0)  # no quality
    errors = validate_observation_structure(_obs(scan=scan))
    assert any("no quality metadata" in e for e in errors)


def test_mismatched_scan_type_fields_flagged():
    """A scan typed ONSD must not carry jugular-only fields - pure structural
    self-consistency, no clinical threshold involved."""
    scan = ScanMeasurement(
        type=ScanType.ONSD, onsd_mm=5.0, jugular_area_mm2=30.0,
        quality=MeasurementQuality(status=QualityStatus.OK),
    )
    errors = validate_observation_structure(_obs(scan=scan))
    assert any("unrelated field" in e for e in errors)


def test_not_taken_quality_with_values_set_flagged():
    scan = ScanMeasurement(type=ScanType.ONSD, onsd_mm=5.0, quality=MeasurementQuality(status=QualityStatus.NOT_TAKEN))
    errors = validate_observation_structure(_obs(scan=scan))
    assert any("NOT_TAKEN" in e for e in errors)


def test_type_specific_fields_without_declared_type_flagged():
    scan = ScanMeasurement(type=None, onsd_mm=5.0)
    errors = validate_observation_structure(_obs(scan=scan))
    assert any("no scan.type declared" in e for e in errors)
