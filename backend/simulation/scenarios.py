"""The four scenario classes from the mission brief, and crew-roster assignment.

`assign_scenarios` (original): a cohort-design choice, not a physiological claim, so
it is implemented deterministically (round-robin over a seeded, shuffled roster) with
no probability distribution invoked. Left completely unchanged for backward
compatibility with any existing caller/test - see `assign_scenarios_with_sans_model`
below for the version `simulation/generator.py` now actually uses.

`assign_scenarios_with_sans_model` (ASTROSENTINEL, 2026-11-04): now that
sans_prior_mapping is approved, the SANS axis of scenario assignment is
probability-grounded (susceptibility class -> event-occurrence rate, both from the
approved assumption) instead of a flat 25% "slow_sans" allocation - a balanced
four-way split would now contradict the approved rates. The VENOUS axis is
deliberately NOT given a probability model here: no venous event prevalence was
approved (and inventing one is explicitly forbidden), so it keeps the same
deterministic, non-probabilistic structural split the original function used. Scenario
D (both outcomes present) still represents coexistence only - crossing two
independently-decided axes never establishes or implies a statistical correlation
between SANS and venous stasis.
"""
from __future__ import annotations

import random

from contracts.models import ScenarioLabel
from registry.loader import Registry
from simulation.physiological_generation import SansSyntheticProfile, generate_sans_susceptibility

SCENARIO_ORDER = [
    ScenarioLabel.HEALTHY,
    ScenarioLabel.SLOW_SANS,
    ScenarioLabel.VENOUS_STASIS,
    ScenarioLabel.BOTH,
]


class ScenarioConfigError(ValueError):
    pass


def validate_scenario_config(crew_size: int, mission_duration_days: int) -> None:
    if crew_size < len(SCENARIO_ORDER):
        raise ScenarioConfigError(
            f"crew_size must be at least {len(SCENARIO_ORDER)} (one per scenario class), got {crew_size}"
        )
    if mission_duration_days != 30:
        raise ScenarioConfigError(
            f"mission_duration_days must be 30 per the documented mission design, got {mission_duration_days}"
        )


def assign_scenarios(crew_size: int, seed: int) -> dict[str, ScenarioLabel]:
    """Deterministic, seeded round-robin assignment of astronaut_id -> scenario.

    Uses the seed only to shuffle astronaut_id order, not to draw any physiological
    or probabilistic value - every astronaut still gets exactly one of the four
    scenario labels in a fixed repeating pattern, so counts stay balanced and
    reproducible for any crew_size.
    """
    astronaut_ids = [f"A{i+1}" for i in range(crew_size)]
    rng = random.Random(seed)
    rng.shuffle(astronaut_ids)

    assignment: dict[str, ScenarioLabel] = {}
    for i, astronaut_id in enumerate(astronaut_ids):
        assignment[astronaut_id] = SCENARIO_ORDER[i % len(SCENARIO_ORDER)]
    return assignment


def scenario_counts(assignment: dict[str, ScenarioLabel]) -> dict[str, int]:
    counts = {s.value: 0 for s in SCENARIO_ORDER}
    for label in assignment.values():
        counts[label.value] += 1
    return counts


def assign_scenarios_with_sans_model(
    crew_size: int, seed: int, registry: Registry
) -> tuple[dict[str, ScenarioLabel], dict[str, SansSyntheticProfile]]:
    """SANS axis: probability-grounded via the approved sans_prior_mapping assumption
    (susceptibility class -> event-occurrence rate). Venous axis: an ungrounded,
    deterministic structural 50/50 split (index parity after a seeded shuffle) - NOT
    a probability draw, since no venous event prevalence is approved and none is
    invented here. Returns both the resulting 4-way labels (for backward-compatible
    reporting/manifest use) and the per-astronaut SANS profile (for the generator to
    use when writing ground truth and physiological values).
    """
    astronaut_ids = [f"A{i+1}" for i in range(crew_size)]
    rng = random.Random(seed)
    rng.shuffle(astronaut_ids)

    profiles: dict[str, SansSyntheticProfile] = {
        aid: generate_sans_susceptibility(aid, seed, registry) for aid in astronaut_ids
    }

    labels: dict[str, ScenarioLabel] = {}
    for i, aid in enumerate(astronaut_ids):
        has_venous = i % 2 == 1  # deterministic structural split, not a probability model
        has_sans = profiles[aid].has_sans_event
        if has_sans and has_venous:
            labels[aid] = ScenarioLabel.BOTH
        elif has_sans:
            labels[aid] = ScenarioLabel.SLOW_SANS
        elif has_venous:
            labels[aid] = ScenarioLabel.VENOUS_STASIS
        else:
            labels[aid] = ScenarioLabel.HEALTHY

    return labels, profiles
