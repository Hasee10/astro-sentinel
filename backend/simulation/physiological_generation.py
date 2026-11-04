"""ASTROSENTINEL: the first physiological generation algorithms this project
implements, now that onsd_baseline_sd_values, onsd_scan_failure_rate, and
sans_prior_mapping are approved (registry/data/assumptions.json, Rahat, 2026-11-04).
Each function here is the concrete "has_implemented_rule" that
simulation.generation_models's readiness-tracking system has been waiting for -
IMPLEMENTED_GENERATION_ALGORITHMS is flipped alongside these in generation_models.py.

What stays blocked, on purpose, even after this module exists:
- The physiological PROGRESSION curve for an astronaut whose has_sans_event is True:
  every astronaut, event-flagged or not, gets only a flat/noisy-around-baseline
  trajectory here - see design_decisions.py::sans_venous_onset_day_assignment,
  still unapproved. No generated ONSD reading carries a detectable disease signal.
  That is an honest limitation, not a bug: inventing a progression shape without an
  approved rule would be exactly the fabrication this project refuses to do.
- jugular_scan_values: still blocked. venous_probability_model/jugular_flow_risk_mapping
  authorize the MONITORING-side Bayesian calculation (monitoring/engine.py), not
  generation of synthetic jugular measurements - no flow-class prevalence/timing rule
  was approved for the generator, and inventing one is not this module's call to make.

All of this is ground-truth/simulation-construction content - the synthetic
susceptibility class, event flag, and time-prior belong on GroundTruthRecord only
(schema v0.5.0), never on anything the monitoring engine or a scheduling policy sees.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from contracts.models import MeasurementQuality, QualityStatus, ScanMeasurement, ScanType
from monitoring.measurement_quality import derive_onsd_quality
from registry.loader import Registry

SYNTHETIC_PRIOR_LABEL = "HYPOTHETICAL SIMULATION ESTIMATE - NOT CLINICALLY VALIDATED"


def _seeded_rng(seed: int, astronaut_id: str, purpose: str) -> random.Random:
    """One independent, deterministic random stream per (seed, astronaut, purpose),
    so e.g. baseline sampling and failure injection never share a stream and
    accidentally correlate with each other."""
    return random.Random(f"{seed}:{astronaut_id}:{purpose}")


# ---------------------------------------------------------------------------
# personal_onsd_baseline_values
# ---------------------------------------------------------------------------


def generate_onsd_baseline(astronaut_id: str, seed: int, registry: Registry) -> float:
    """Clipped-normal per-astronaut baseline, mm. Draws Normal(mean, sd) then clips
    (not resamples) to the approved range - see onsd_baseline_sd_values."""
    config = registry.assumptions["onsd_baseline_sd_values"].value_or_range
    mean = config["between_astronaut_mean_mm"]
    sd = config["between_astronaut_sd_mm"]
    low, high = config["clip_range_mm"]
    rng = _seeded_rng(seed, astronaut_id, "onsd_baseline")
    raw = rng.gauss(mean, sd)
    return min(max(raw, low), high)


# ---------------------------------------------------------------------------
# onsd_scan_values + measurement_quality_failure_injection (one synthetic scan)
# ---------------------------------------------------------------------------


def generate_onsd_scan(astronaut_id: str, day: int, baseline_mm: float, seed: int, registry: Registry) -> ScanMeasurement:
    """One day's synthetic ONSD scan: baseline + within-person Gaussian drift, with
    failure injection per onsd_scan_failure_rate. No progression signal is added for
    any astronaut, event-flagged or not - see module docstring."""
    sd_config = registry.assumptions["onsd_baseline_sd_values"].value_or_range
    within_person_sd = sd_config["within_person_sd_mm_base"]
    failure_config = registry.assumptions["onsd_scan_failure_rate"].value_or_range

    drift_rng = _seeded_rng(seed, astronaut_id, f"onsd_drift_day{day}")
    reading = baseline_mm + drift_rng.gauss(0.0, within_person_sd)

    failure_rng = _seeded_rng(seed, astronaut_id, f"onsd_failure_day{day}")
    fails = failure_rng.random() < (failure_config["base_failure_rate_pct"] / 100.0)
    if not fails:
        scan = ScanMeasurement(type=ScanType.ONSD, onsd_mm=reading, on_axis=True)
        # Reuses, not duplicates, the existing sourced on-axis rule - every
        # generated record is structurally complete (quality already set) rather
        # than relying on a later caller to derive it lazily.
        return scan.model_copy(update={"quality": derive_onsd_quality(scan)})

    type_rng = _seeded_rng(seed, astronaut_id, f"onsd_failure_type_day{day}")
    off_axis_fraction = failure_config["failure_type_split_pct"]["off_axis"] / 100.0
    if type_rng.random() < off_axis_fraction:
        bias = failure_config["off_axis_positive_bias_mm"]["operational_value_in_use"]
        scan = ScanMeasurement(type=ScanType.ONSD, onsd_mm=reading + bias, on_axis=False)
        return scan.model_copy(update={"quality": derive_onsd_quality(scan)})

    return ScanMeasurement(
        type=ScanType.ONSD,
        onsd_mm=None,
        on_axis=None,
        quality=MeasurementQuality(
            status=QualityStatus.FAILED,
            reasons=["air under eyelid dressing (onsd_technical_artifacts: documented technical artifact)"],
            weight=0.0,
        ),
    )


# ---------------------------------------------------------------------------
# SANS synthetic susceptibility / event-occurrence - ground-truth bookkeeping only
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SansSyntheticProfile:
    is_high_susceptibility: bool
    has_sans_event: bool  # evaluation-only; never implies a generated progression signal

    def synthetic_prior_pct(self, day: int, registry: Registry) -> float:
        """Time-incrementing SYNTHETIC prior for ground-truth bookkeeping only - never
        written to assess_history()'s probability.sans (see sans_prior_mapping's
        note). Always label SYNTHETIC_PRIOR_LABEL wherever this is shown."""
        config = registry.assumptions["sans_prior_mapping"].value_or_range
        start = config["starting_synthetic_prior_pct"]["high" if self.is_high_susceptibility else "low"]
        increment = config["time_increment_pct_points_per_day"]
        cap = config["max_synthetic_prior_pct"]
        return min(start + increment * (day - 1), cap)


def generate_sans_susceptibility(astronaut_id: str, seed: int, registry: Registry) -> SansSyntheticProfile:
    config = registry.assumptions["sans_prior_mapping"].value_or_range

    susceptibility_rng = _seeded_rng(seed, astronaut_id, "sans_susceptibility")
    high_fraction = config["susceptibility_split_pct"]["high"] / 100.0
    is_high = susceptibility_rng.random() < high_fraction

    event_rng = _seeded_rng(seed, astronaut_id, "sans_event_occurrence")
    event_probability = config["event_occurrence_probability_pct"]["high" if is_high else "low"] / 100.0
    has_event = event_rng.random() < event_probability

    return SansSyntheticProfile(is_high_susceptibility=is_high, has_sans_event=has_event)
