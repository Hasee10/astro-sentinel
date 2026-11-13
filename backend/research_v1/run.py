"""Executable gated engineering study; never publishes or claims signed approval.

python -m research_v1.run --engineering-fixture --output-dir outputs/recovery_fixture
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean

from contracts.models import AstronautDayObservation, ObservationMetadata, ScanSession
from evaluation.metrics import detection_delay, false_escalations, is_missed_event
from research_v1.authorization import SPEC, SPEC_SHA256, authorize
from research_v1.monitoring import assess
from research_v1.physiology import acquire, make_case, triggers
from research_v1.scheduling import DayView, decide


def run_case(case, policy, sensitivity=0.7, half_life=7, *, explicit_red_flag_days=()):
    history, assessments, decisions = [], [], []
    last_session, last_usable, retry_due, previous = None, None, None, None
    recent = []
    # A synthetic preflight input, not the hidden event flag or future onset.
    preflight_prior = case.preflight.starting_sans_prior_pct
    for day in range(1, 31):
        flags = triggers(case, day, sensitivity)  # generator only; return booleans
        if any(flags.values()):
            recent.append(day)
        view = DayView(day, last_session, last_usable, retry_due,
                       previous.sans.tier.value if previous else "unresolved",
                       previous.venous.tier.value if previous else "unresolved", tuple(recent))
        scheduled, reason = decide(view, policy)
        is_retry = scheduled and reason == "failed_acquisition_retry"
        obs = AstronautDayObservation(astronaut_id=case.astronaut_id, day=day,
            metadata=ObservationMetadata(run_id=f"engineering-{case.seed}", synthetic_label=SPEC["label"],
                acquisition_policy=policy, scheduling_reason=reason))
        obs.metadata.observable_triggers = flags
        if scheduled:
            measurements = acquire(case, day)
            if day in explicit_red_flag_days:
                measurements[0].red_flag_symptom = True
            obs.scan_session = ScanSession(session_id=f"{case.astronaut_id}:{day}", policy=policy,
                reason_codes=[reason], is_retry=is_retry, measurements=measurements)
            if day in explicit_red_flag_days:
                obs.scan_session.reason_codes.append("explicit_engineering_red_flag_input")
            last_session = day
            usable = all(m.quality.status.value == "ok" for m in measurements)
            if usable:
                last_usable = day
            # One next-day retry per original session; a retry never recursively
            # creates another mandatory retry. Tier follow-up remains separate.
            retry_due = day + 1 if not usable and not is_retry else None
        history.append(obs)
        previous = assess(history, preflight_prior, half_life=half_life, previous=previous)
        assessments.append(previous)
        decisions.append({"astronaut_id": case.astronaut_id, "day": day, "policy": policy,
                          "scan_scheduled": scheduled, "reason": reason,
                          "observable_trigger": flags, "last_usable_session_day": last_usable,
                          "next_retry_day": retry_due, "label": SPEC["label"]})
    return history, assessments, decisions


def summarize_case(case, history, assessments):
    sessions = [o.scan_session for o in history if o.scan_session]
    measurements = [m for s in sessions for m in s.measurements]
    result = {"sessions": len(sessions), "repeat_sessions": sum(s.is_retry for s in sessions),
              "successful_measurements": sum(m.quality.status.value == "ok" for m in measurements),
              "degraded_measurements": sum(m.quality.status.value == "degraded" for m in measurements),
              "failed_measurements": sum(m.quality.status.value == "failed" for m in measurements)}
    for outcome, onset in (("sans", case.sans_onset), ("venous", case.venous_onset)):
        physiological = [a.as_of_day for a in assessments
            if getattr(a, outcome).tier.value in {"repeat", "consult", "urgent"}
            and getattr(a, outcome).tier_reason.value != "measurement_quality"
            and getattr(a, outcome).evidence_day is not None
            and (onset is None or getattr(a, outcome).evidence_day >= onset)]
        serious = [a.as_of_day for a in assessments if getattr(a, outcome).tier.value in {"consult", "urgent"}]
        result[outcome] = {"has_event": onset is not None, "delay": detection_delay(onset, physiological),
            "missed": is_missed_event(onset, physiological, 30),
            "false_escalation_days": false_escalations(serious, onset),
            "falsely_escalated_astronaut": onset is None and bool(serious),
            "tiers": dict(Counter(getattr(a, outcome).tier.value for a in assessments))}
    return result


def study(output_dir, *, engineering_fixture=False, crew_size=60, seeds=(42, 43, 44), sensitivities=None, half_lives=None):
    label = authorize(engineering_fixture=engineering_fixture)
    if crew_size < 1 or not seeds:
        raise ValueError("A nonempty cohort and seeds are required")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    sensitivities = sensitivities or SPEC["trigger"]["sweep"]
    half_lives = half_lives or SPEC["monitoring"]["half_life_sweep_days"]
    for seed in seeds:
        cohort = [make_case(f"A{i + 1}", seed) for i in range(crew_size)]
        for half_life in half_lives:
            for sensitivity in sensitivities:
                for policy in ("fixed", "adaptive_replacement"):
                    totals = []
                    for case in cohort:
                        history, assessments, _ = run_case(case, policy, sensitivity, half_life)
                        totals.append(summarize_case(case, history, assessments))
                    row = {"label": label, "seed": seed, "crew_size": crew_size, "days": 30,
                           "half_life_days": half_life, "trigger_sensitivity": sensitivity, "policy": policy}
                    for key in ("sessions", "repeat_sessions", "successful_measurements", "degraded_measurements", "failed_measurements"):
                        row[key] = sum(t[key] for t in totals)
                    for outcome in ("sans", "venous"):
                        delays = [t[outcome]["delay"] for t in totals if t[outcome]["delay"] is not None]
                        tiers = Counter()
                        for t in totals:
                            tiers.update(t[outcome]["tiers"])
                        row[outcome] = {"synthetic_events": sum(t[outcome]["has_event"] for t in totals),
                            "detected_events": len(delays), "mean_detection_delay": mean(delays) if delays else None,
                            "missed_events": sum(t[outcome]["missed"] for t in totals),
                            "false_escalation_days": sum(t[outcome]["false_escalation_days"] for t in totals),
                            "falsely_escalated_astronauts": sum(t[outcome]["falsely_escalated_astronaut"] for t in totals),
                            "tier_distribution": dict(tiers)}
                    rows.append(row)
    differences = []
    for index in range(0, len(rows), 2):
        fixed, adaptive = rows[index:index + 2]
        diff = {k: fixed[k] for k in ("label", "seed", "half_life_days", "trigger_sensitivity")}
        diff["adaptive_minus_fixed_sessions"] = adaptive["sessions"] - fixed["sessions"]
        for outcome in ("sans", "venous"):
            f, a = fixed[outcome], adaptive[outcome]
            diff[outcome] = {"missed_events_difference": a["missed_events"] - f["missed_events"],
                "false_escalation_days_difference": a["false_escalation_days"] - f["false_escalation_days"],
                "mean_delay_difference": a["mean_detection_delay"] - f["mean_detection_delay"]
                    if a["mean_detection_delay"] is not None and f["mean_detection_delay"] is not None else None}
        differences.append(diff)
    report = {"label": label, "validated_for_experiment": False, "spec_version": SPEC["version"], "spec_sha256": SPEC_SHA256,
              "seeds": list(seeds), "cohort_size_per_seed": crew_size, "rows": rows, "paired_differences": differences,
              "metric_definitions": {"sessions": "One shared session regardless of two attempted measurements",
                  "detection": "Repeat or higher from physiological evidence acquired on/after onset; technical quality Repeat excluded",
                  "delay": "Mean among detected events only; missed count always reported alongside",
                  "false_escalations": "Healthy outcome reaching Consult/Urgent, counted per assessment day per mission convention; unique astronauts also reported"},
              "crossover": "No validated crossover claim: model and precedence remain pending independent confirmation. Raw paired differences are available for engineering inspection.",
              "limitations": SPEC["unresolved_interpretations"]}
    (output_dir / "engineering_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for scenario in ("healthy", "sans", "venous", "both"):
        case = make_case(f"DEMO-{scenario}", seeds[0], scenario)
        history, assessments, decisions = run_case(case, "adaptive_replacement")
        demo_dir = output_dir / scenario
        demo_dir.mkdir(exist_ok=True)
        for name, records in (("observations", history), ("assessments", assessments)):
            (demo_dir / f"{name}.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
        (demo_dir / "decisions.json").write_text(json.dumps(decisions, indent=2), encoding="utf-8")
        (demo_dir / "ground_truth_PRIVATE.json").write_text(json.dumps({"label": label, "sans_onset": case.sans_onset, "venous_onset": case.venous_onset}, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engineering-fixture", action="store_true")
    parser.add_argument("--crew-size", type=int, default=60)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = study(args.output_dir, engineering_fixture=args.engineering_fixture, crew_size=args.crew_size)
    except PermissionError as exc:
        print(str(exc))
        return 2
    print(json.dumps({k: report[k] for k in ("label", "validated_for_experiment", "seeds", "cohort_size_per_seed", "spec_sha256")}))
    print(f"Wrote {len(report['rows'])} engineering comparison rows to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
