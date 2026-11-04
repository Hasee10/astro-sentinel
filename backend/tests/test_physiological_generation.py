"""ASTROSENTINEL: tests for simulation/physiological_generation.py - the ONSD
baseline/scan/failure-injection and SANS synthetic susceptibility/prior algorithms."""
from __future__ import annotations

import pytest

from contracts.models import QualityStatus, ScanType
from registry.loader import load_all
from simulation.physiological_generation import (
    SYNTHETIC_PRIOR_LABEL,
    generate_onsd_baseline,
    generate_onsd_scan,
    generate_sans_susceptibility,
)


@pytest.fixture(scope="module")
def registry():
    return load_all()


# ---- ONSD baseline ----


def test_onsd_baseline_stays_within_approved_clip_range(registry):
    config = registry.assumptions["onsd_baseline_sd_values"].value_or_range
    low, high = config["clip_range_mm"]
    for i in range(300):
        b = generate_onsd_baseline(f"A{i}", seed=1, registry=registry)
        assert low <= b <= high


def test_onsd_baseline_deterministic_for_fixed_seed(registry):
    a = generate_onsd_baseline("A1", seed=42, registry=registry)
    b = generate_onsd_baseline("A1", seed=42, registry=registry)
    assert a == b


def test_onsd_baseline_differs_across_astronauts_for_same_seed(registry):
    values = {generate_onsd_baseline(f"A{i}", seed=42, registry=registry) for i in range(20)}
    assert len(values) > 1  # not literally the same draw for everyone


def test_onsd_baseline_spread_matches_approved_sd_within_tolerance(registry):
    config = registry.assumptions["onsd_baseline_sd_values"].value_or_range
    mean, sd = config["between_astronaut_mean_mm"], config["between_astronaut_sd_mm"]
    samples = [generate_onsd_baseline(f"A{i}", seed=7, registry=registry) for i in range(2000)]
    observed_mean = sum(samples) / len(samples)
    assert abs(observed_mean - mean) < 0.05  # clipping biases this slightly inward, generous tolerance


# ---- ONSD scan / failure injection ----


def test_onsd_scan_failure_rate_matches_approved_rate(registry):
    config = registry.assumptions["onsd_scan_failure_rate"].value_or_range
    expected_rate = config["base_failure_rate_pct"] / 100.0
    n = 5000
    fails = sum(
        1
        for i in range(n)
        if generate_onsd_scan(f"B{i}", 1, 5.35, seed=3, registry=registry).onsd_mm is None
        or generate_onsd_scan(f"B{i}", 1, 5.35, seed=3, registry=registry).on_axis is False
    )
    assert abs(fails / n - expected_rate) < 0.02


def test_onsd_scan_quality_always_set_never_left_for_caller_to_derive(registry):
    """score_crew.py's structural validator requires quality metadata whenever a
    scan is present - the generator must never rely on a later caller to fill it
    in, even though monitoring/measurement_quality.py's deriver could."""
    for i in range(200):
        scan = generate_onsd_scan(f"C{i}", i % 30 + 1, 5.35, seed=11, registry=registry)
        assert scan.quality is not None


def test_onsd_scan_off_axis_failure_uses_deterministic_bias_not_a_distribution(registry):
    """The approved bias is a fixed constant (midpoint of [0.3, 0.5]mm), not sampled
    from any distribution - every off-axis reading must clear baseline+bias minus a
    generous allowance for the separate, independent drift noise term."""
    config = registry.assumptions["onsd_scan_failure_rate"].value_or_range
    expected_bias = config["off_axis_positive_bias_mm"]["operational_value_in_use"]
    off_axis_found = False
    for i in range(500):
        scan = generate_onsd_scan(f"E{i}", 1, 5.35, seed=13, registry=registry)
        if scan.on_axis is False:
            off_axis_found = True
            assert scan.onsd_mm >= 5.35 + expected_bias - 1.0  # within generous drift-noise tolerance
            assert scan.quality.status == QualityStatus.DEGRADED
    assert off_axis_found


def test_onsd_scan_air_under_dressing_failure_has_no_usable_value(registry):
    found_failed = False
    for i in range(500):
        scan = generate_onsd_scan(f"F{i}", 1, 5.35, seed=17, registry=registry)
        if scan.quality is not None and scan.quality.status == QualityStatus.FAILED:
            found_failed = True
            assert scan.onsd_mm is None
            assert scan.on_axis is None
    assert found_failed


def test_onsd_scan_type_is_always_onsd(registry):
    for i in range(50):
        scan = generate_onsd_scan(f"G{i}", 1, 5.35, seed=19, registry=registry)
        assert scan.type == ScanType.ONSD


def test_onsd_scan_deterministic_for_fixed_seed(registry):
    a = generate_onsd_scan("A1", 5, 5.35, seed=42, registry=registry)
    b = generate_onsd_scan("A1", 5, 5.35, seed=42, registry=registry)
    assert a == b


# ---- SANS synthetic susceptibility / event occurrence / time-prior ----


def test_susceptibility_split_matches_approved_rate(registry):
    config = registry.assumptions["sans_prior_mapping"].value_or_range
    expected_high_fraction = config["susceptibility_split_pct"]["high"] / 100.0
    n = 4000
    high = sum(generate_sans_susceptibility(f"A{i}", seed=5, registry=registry).is_high_susceptibility for i in range(n))
    assert abs(high / n - expected_high_fraction) < 0.03


def test_event_fraction_matches_expected_overall_rate(registry):
    """75% low x 30% + 25% high x 70% = 40% expected overall - the document's own
    internal consistency check, verified against the actual generator output."""
    config = registry.assumptions["sans_prior_mapping"].value_or_range
    expected = config["expected_overall_event_fraction_pct"] / 100.0
    n = 4000
    events = sum(generate_sans_susceptibility(f"B{i}", seed=9, registry=registry).has_sans_event for i in range(n))
    assert abs(events / n - expected) < 0.03


def test_susceptibility_deterministic_for_fixed_seed(registry):
    a = generate_sans_susceptibility("A1", seed=42, registry=registry)
    b = generate_sans_susceptibility("A1", seed=42, registry=registry)
    assert a == b


def test_synthetic_prior_arithmetic_matches_approved_formula(registry):
    config = registry.assumptions["sans_prior_mapping"].value_or_range
    profile_low = next(
        generate_sans_susceptibility(f"L{i}", seed=100, registry=registry)
        for i in range(500)
        if not generate_sans_susceptibility(f"L{i}", seed=100, registry=registry).is_high_susceptibility
    )
    start = config["starting_synthetic_prior_pct"]["low"]
    increment = config["time_increment_pct_points_per_day"]
    assert profile_low.synthetic_prior_pct(1, registry) == start
    assert profile_low.synthetic_prior_pct(5, registry) == pytest.approx(start + increment * 4)


def test_synthetic_prior_caps_at_approved_maximum(registry):
    config = registry.assumptions["sans_prior_mapping"].value_or_range
    cap = config["max_synthetic_prior_pct"]
    profile = generate_sans_susceptibility("Z1", seed=42, registry=registry)
    assert profile.synthetic_prior_pct(10000, registry) == cap


def test_synthetic_prior_label_is_the_required_disclaimer():
    assert SYNTHETIC_PRIOR_LABEL == "HYPOTHETICAL SIMULATION ESTIMATE - NOT CLINICALLY VALIDATED"


def test_off_axis_bias_midpoint_is_flagged_pending_not_approved(registry):
    """ASTROSENTINEL correction (2026-11-04), Part 3A: Rahat approved the bias
    RANGE (0.3-0.5mm), not this project's own choice of the midpoint as the
    operational realization within it - that choice must read as pending, at a
    visibly lower confidence than the surrounding approved numbers (rate, split,
    range), not silently presented as equally confirmed."""
    bias_config = registry.assumptions["onsd_scan_failure_rate"].value_or_range["off_axis_positive_bias_mm"]
    assert bias_config["operational_value_in_use"] == 0.4
    assert bias_config["range"] == [0.3, 0.5]
    assert "PENDING" in bias_config["operational_value_status"]
    assert "not itself separately approved" in bias_config["operational_value_status"]
