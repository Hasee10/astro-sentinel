"""ASTROSENTINEL: the approved trigger-firing simulation model.

registry/design_decisions.py::DESIGN_DECISIONS["trigger_firing_simulation_model"]
(approved by Rahat, 2026-11-04): a windowed sensitivity model. Within the 5-day
window starting at a case's hidden onset day for an outcome, the trigger fires
independently each day with probability h = 1 - (1-s)**(1/5), chosen so the
cumulative chance of firing at least once across the window equals the assumed
accuracy s (hrv_trigger_assumed_accuracy). Outside that window - including every day
of a case with no onset for the outcome - the trigger fires at an independent base
false-fire rate (also from hrv_trigger_assumed_accuracy).

"Accuracy" (s) here is NOT classifier sensitivity/specificity/overall diagnostic
accuracy - it is a scheduling-detection usefulness parameter local to this trigger
model only (see the design decision's own text).

The trigger is wired to SANS onset only, never venous: the weak signal it stands in
for (HRV drift) has a hypothesized SANS link in the parameter sheet
(hrv_onsd_coefficient) and no venous link anywhere in it - an explicit, documented
interpretive choice, consistent with how monitoring/engine.py routes
SANS_SCAN_TYPES/VENOUS_SCAN_TYPES.

Ground-truth isolation, matching evaluation/sweep.py's existing boundary exactly:
1. `build_trigger_schedules()` - the "signal generator" step (BLOCKER_QUESTIONS.md
   items 8-9: "the synthetic signal generator may use evaluation-only onset truth").
   Takes HiddenGroundTruth for the cohort and the full list of swept accuracy values;
   runs entirely BEFORE any scheduling decision is made, outside the policy loop.
2. `make_precomputed_trigger_fn()` wraps the result as a TriggerFn
   (Callable[[PolicyDayView, float], bool]) that performs ONLY a dictionary lookup
   keyed by (assumed_accuracy, case_id, day) - it never reads an onset day, or
   anything else beyond what PolicyDayView already restricts, at call time. This is
   "the policy may use ONLY the generated observable flag, NEVER hidden onset truth."
"""
from __future__ import annotations

import random
from typing import Sequence

from evaluation.sweep import HiddenGroundTruth, ObservableCase, PolicyDayView

POST_ONSET_WINDOW_DAYS = 5
TRIGGER_OUTCOME = "sans"  # see module docstring for why


def per_day_firing_probability(assumed_accuracy: float, window_days: int = POST_ONSET_WINDOW_DAYS) -> float:
    """h = 1 - (1 - s) ** (1 / window_days) - the approved formula."""
    if not (0.0 <= assumed_accuracy <= 1.0):
        raise ValueError(f"assumed_accuracy must be in [0, 1], got {assumed_accuracy}")
    if window_days < 1:
        raise ValueError(f"window_days must be >= 1, got {window_days}")
    return 1.0 - (1.0 - assumed_accuracy) ** (1.0 / window_days)


def build_trigger_schedules(
    cohort: Sequence[tuple[ObservableCase, HiddenGroundTruth]],
    accuracy_values: Sequence[float],
    base_false_fire_probability: float,
    seed: int,
    window_days: int = POST_ONSET_WINDOW_DAYS,
) -> dict[float, dict[tuple[str, int], bool]]:
    """Evaluation-only step: reads HiddenGroundTruth. Returns, for each swept
    accuracy value, a {(case_id, day): fired} lookup table covering every day of
    every case. Deterministic for a fixed seed; independent per (accuracy, case,
    day) draw so sweeping accuracy doesn't just rescale a shared random stream."""
    schedules: dict[float, dict[tuple[str, int], bool]] = {}
    for accuracy in accuracy_values:
        h = per_day_firing_probability(accuracy, window_days)
        schedule: dict[tuple[str, int], bool] = {}
        for observable, ground_truth in cohort:
            onset = ground_truth.onset_day(TRIGGER_OUTCOME)
            rng = random.Random(f"{seed}:{observable.case_id}:trigger:{accuracy}")
            for day in observable.days:
                in_window = onset is not None and onset <= day < onset + window_days
                probability = h if in_window else base_false_fire_probability
                schedule[(observable.case_id, day)] = rng.random() < probability
        schedules[accuracy] = schedule
    return schedules


def make_precomputed_trigger_fn(schedules: dict[float, dict[tuple[str, int], bool]]):
    """Wraps precomputed schedules as a TriggerFn: Callable[[PolicyDayView, float], bool].
    A pure lookup - no onset-day access, and nothing beyond `day_view.case_id`/
    `day_view.day` is ever read from the restricted view, at call time."""

    def _trigger_fn(day_view: PolicyDayView, assumed_accuracy: float) -> bool:
        schedule = schedules.get(assumed_accuracy)
        if schedule is None:
            raise KeyError(
                f"no precomputed trigger schedule for assumed_accuracy={assumed_accuracy!r} "
                f"- build_trigger_schedules() must be called with every value that will be swept"
            )
        return schedule.get((day_view.case_id, day_view.day), False)

    return _trigger_fn
