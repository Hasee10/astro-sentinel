"""Private latent case construction and deterministic potential acquisitions.

Never pass Case to a scheduler or monitoring function. Independent streams make
policy comparisons use identical measurements for a given astronaut/day/outcome.
"""
from dataclasses import dataclass
import random

from contracts.models import MeasurementQuality, QualityStatus, ScanMeasurement, ScanType
from research_v1.authorization import SPEC


def rng(seed, astronaut, purpose):
    return random.Random(f"{seed}:{astronaut}:{purpose}")


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class PreflightInputs:
    """Explicit fictional preflight observations; no event label or onset."""
    astronaut_id: str
    starting_sans_prior_pct: float


@dataclass(frozen=True)
class Case:
    astronaut_id: str
    seed: int
    high: bool
    sans_onset: int | None
    venous_onset: int | None
    onsd_baseline: float
    sans_amplitude: float
    sans_ramp: int
    jugular_baseline: float
    jugular_multiplier: float
    retrograde: bool
    preflight: PreflightInputs


def make_case(astronaut_id, seed, demonstration=None):
    s, v = SPEC["sans"], SPEC["venous"]
    high = rng(seed, astronaut_id, "susceptibility").random() < s["high_fraction"]
    sans = rng(seed, astronaut_id, "sans_event").random() < s["event_high" if high else "event_low"]
    venous = rng(seed, astronaut_id, "venous_event").random() < v["event_probability"]
    if demonstration is not None:
        sans, venous = demonstration in {"sans", "both"}, demonstration in {"venous", "both"}
    baseline = clamp(rng(seed, astronaut_id, "onsd_baseline").gauss(s["baseline_mean_mm"], s["baseline_sd_mm"]), *s["baseline_clip_mm"])
    vrng = rng(seed, astronaut_id, "jugular_baseline")
    jugular_baseline = vrng.gauss(v["baseline_mm2"], v["baseline_mm2"] * v["baseline_sd_fraction"])
    while jugular_baseline <= 0 or jugular_baseline > v["synthetic_cap_mm2"]:
        jugular_baseline = vrng.gauss(v["baseline_mm2"], v["baseline_mm2"] * v["baseline_sd_fraction"])
    return Case(astronaut_id, seed, high,
                (s["demonstration_onset"] if demonstration else rng(seed, astronaut_id, "sans_onset").randint(*s["onset_days"])) if sans else None,
                (v["demonstration_onset"] if demonstration else rng(seed, astronaut_id, "venous_onset").randint(*v["onset_days"])) if venous else None,
                baseline,
                s["demonstration_amplitude_mm"] if demonstration else rng(seed, astronaut_id, "amplitude").uniform(*s["amplitude_mm"]),
                s["demonstration_ramp_days"] if demonstration else rng(seed, astronaut_id, "ramp").randint(*s["ramp_days"]),
                jugular_baseline, rng(seed, astronaut_id, "area_multiplier").uniform(*v["area_multiplier"]),
                rng(seed, astronaut_id, "retrograde_event").random() < v["retrograde_fraction"],
                PreflightInputs(astronaut_id, s["prior_high_pct" if high else "prior_low_pct"]))


def latent(case, day):
    s, v = SPEC["sans"], SPEC["venous"]
    progress = 0 if case.sans_onset is None else clamp((day - case.sans_onset) / case.sans_ramp, 0, 1)
    onsd = case.onsd_baseline + case.sans_amplitude * progress
    vp = 0 if case.venous_onset is None else clamp((day - case.venous_onset) / v["ramp_days"], 0, 1)
    area = min(v["synthetic_cap_mm2"], case.jugular_baseline * (1 + (case.jugular_multiplier - 1) * vp))
    flow = "antegrade"
    active = case.venous_onset is not None and day >= case.venous_onset
    if active and day >= case.venous_onset + v["stagnant_after_days"]:
        flow = "stagnant"
    if active and case.retrograde and day >= case.venous_onset + v["retrograde_after_days"]:
        flow = "retrograde"
    if not active:
        draw = rng(case.seed, case.astronaut_id, f"false_flow:{day}").random()
        if draw < v["healthy_false_retrograde"]:
            flow = "retrograde"
        elif draw < v["healthy_false_retrograde"] + v["healthy_false_stagnant"]:
            flow = "stagnant"
    return onsd, area, flow


def acquire(case, day):
    s, v = SPEC["sans"], SPEC["venous"]
    onsd, area, flow = latent(case, day)
    onsd += rng(case.seed, case.astronaut_id, f"within:{day}").gauss(0, s["within_person_sd_mm"])
    onsd += rng(case.seed, case.astronaut_id, f"observer:{day}").gauss(0, s["observer_sd_mm"])
    area = max(0, area + rng(case.seed, case.astronaut_id, f"area_noise:{day}").gauss(0, area * v["measurement_noise_fraction"]))
    scans = []
    for outcome in ("sans", "venous"):
        failed = rng(case.seed, case.astronaut_id, f"quality:{outcome}:{day}").random() < SPEC["acquisition"]["failure_probability"]
        degraded = failed and rng(case.seed, case.astronaut_id, f"failure_type:{outcome}:{day}").random() < 0.5
        status = QualityStatus.DEGRADED if degraded else QualityStatus.FAILED if failed else QualityStatus.OK
        q = MeasurementQuality(status=status, reasons=["Synthetic technical acquisition artifact"] if failed else [],
                               weight=s["poor_log_weight"] if degraded else 0 if failed else 1)
        if outcome == "sans":
            scans.append(ScanMeasurement(type=ScanType.ONSD, onsd_mm=None if status == QualityStatus.FAILED else onsd + (0.4 if degraded else 0),
                        onsd_baseline_mm=case.onsd_baseline, on_axis=not failed, quality=q))
        else:
            scans.append(ScanMeasurement(type=ScanType.JUGULAR, jugular_area_mm2=None if status == QualityStatus.FAILED else area,
                        jugular_baseline_mm2=case.jugular_baseline, jugular_flow_class=None if status == QualityStatus.FAILED else flow, quality=q))
    return scans


def triggers(case, day, sensitivity):
    result = {}
    for outcome, onset in (("sans", case.sans_onset), ("venous", case.venous_onset)):
        in_window = onset is not None and onset <= day < onset + SPEC["trigger"]["window_days"]
        probability = 1 - (1 - sensitivity) ** (1 / SPEC["trigger"]["window_days"]) if in_window else SPEC["trigger"]["false_fire_probability"]
        result[outcome] = rng(case.seed, case.astronaut_id, f"trigger:{outcome}:{day}").random() < probability
    return result
