"""The four scenario classes from the mission brief, and crew-roster assignment.

Assignment (which astronaut gets which scenario) is a cohort-design choice, not a
physiological claim, so it is implemented deterministically here (round-robin over a
seeded, shuffled roster) with no probability distribution invoked. Scenario D (both
outcomes present) represents coexistence only - it must never be read as establishing
a statistical correlation between SANS and venous stasis.
"""
from __future__ import annotations

import random

from contracts.models import ScenarioLabel

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
