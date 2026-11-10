# Proposed `sans_physiological_progression` model — for Rahat's review only

**Status: NOT APPROVED — but fully implemented and tested, ready to activate.**
`registry/design_decisions.py::sans_physiological_progression` is still
`approved=False`. As of 2026-11-10, the exact formula below now exists as
`simulation/physiological_generation.py::generate_sans_progression_offset()`,
with tests proving it returns `0.0` unconditionally against today's real,
unapproved registry — confirmed by regenerating the published demo run and
diffing it byte-for-byte against the version already on GitHub: identical.
**The only remaining step is Rahat's explicit yes/no on the specific number
below** — not an engineering task, just a decision. Once he sets `approved=True`,
`decision_text`, and `approved_by="Rahat"` on that entry, the formula activates
with no further code changes.

## Where this came from

Haseeb was given an **external/public** CSV (`Synthetic_Astronaut_SANS_Simulation_20000.csv`,
20,000 synthetic astronauts × 30 days = 600,000 rows) and asked to characterize
what progression rule it implies, strictly as a candidate for Rahat to approve
or reject — not to treat it as validated science. The analysis below is purely
statistical (pandas/scipy on the raw CSV); nothing from it has been written
into the codebase.

**Important caveat up front:** this CSV is *not* a cited study, not from Rahat,
and not from the mission document's parameter sheet. It should be judged the
same way any unsourced external dataset would be — on whether its proposed
rule is one Rahat is willing to sign off on as a synthetic-design choice, not
on the assumption that whoever built it did rigorous science.

## What the CSV's OTHER columns already match (not new — context only)

Three of the CSV's columns are statistically indistinguishable from assumptions
**already approved** in our registry, which is why this looked worth analyzing
in the first place rather than discarding outright:

| CSV behavior | Matches approved assumption |
|---|---|
| Healthy-astronaut daily ONSD scatter around personal baseline: mean ≈ 0.000mm, SD ≈ 0.200mm (n=324,566 OK-quality readings) | `onsd_baseline_sd_values.within_person_sd_mm_base = 0.2` exactly |
| Scan quality: 90.0% OK / 5.0% Off-Axis / 5.0% Poor | `onsd_scan_failure_rate`: 10% base failure, 50/50 off-axis/air-under-dressing split — exactly |
| Susceptibility_Class Low/High with Starting_Prior 0.05/0.10 | `sans_prior_mapping`'s approved Low=5%/High=10% starting prior split |

This is why the progression signal below is worth isolating cleanly — the rest
of the CSV's generative model appears to already be built on our approved
numbers, so the progression rule is the one genuinely new thing in it.

## The progression signal itself

Isolated as `delta = Measured_ONSD - Personal_Baseline_ONSD`, OK-quality scans
only, for the 7,989 astronauts with a real `Onset_Day` (excludes NaN/degraded
readings so measurement artifacts aren't mistaken for physiology):

- **Pre-onset**, sick-cohort astronauts: mean delta ≈ −0.0005mm, SD ≈ 0.1997mm —
  statistically identical to the healthy-cohort null above. Good sign: no
  backward-in-time leakage in this CSV's generation.
- **Post-onset**, pooled across both susceptibility classes, binned by days
  since onset (n=7,175 at day 0 down to n=952 at day 25):

  | Days since onset | 0 | 5 | 10 | 15 | 20 | 25 |
  |---|---|---|---|---|---|---|
  | Mean delta (mm) | 0.001 | 0.198 | 0.396 | 0.598 | 0.810 | 1.004 |

  This is a **clean straight line**: weighted least-squares gives
  `delta ≈ 0.0400 × days_since_onset` (intercept ≈ 0, as expected — day 0 is
  the onset day itself). The day-to-day noise SD stays ≈ 0.20mm throughout —
  identical to the healthy baseline's noise. In other words, this CSV's model
  (if that's what it is) looks like: **take the same already-approved
  baseline + 0.2mm daily noise, and add a deterministic mean shift of
  +0.04mm per day since onset, with no change to the noise itself.**
- **Low vs. High susceptibility class**: the slope is the same (~0.04mm/day)
  in both groups to within noise — Susceptibility_Class in this CSV appears to
  only affect *who* gets sick and the starting prior (already approved), not
  *how fast* ONSD changes once sick.
- **Tail flattening (days 23-27, delta ≈ 0.96-1.00mm) is NOT reliable evidence
  of a plateau.** The sample size collapses through that range (952 → 328 →
  0 by day 28) because only astronauts whose onset happened very early in the
  30-day mission can reach a high days-since-onset value at all — a
  survivorship effect, not necessarily biology. I am explicitly flagging this
  rather than claiming the CSV shows a ceiling; a true cap, if one exists,
  would need to be a separate, explicit decision, not inferred from this tail.

## The exact candidate rule, if you choose to approve something

```
measured_onsd(day) = personal_baseline_onsd
                    + 0.04 * max(0, day - onset_day)      [mm, linear, no cap]
                    + N(0, within_person_sd_mm)            [same noise already approved]
```

using whichever `within_person_sd_mm` sweep point is active from the already-
approved `onsd_baseline_sd_values` (base 0.2, swept [0.1, 0.2, 0.3]) — this
proposal does not touch that.

## Decision needed from Rahat

- **Exact missing input/rule:** the slope (and optional cap) of ONSD increase
  per day after SANS onset.
- **Parameter-sheet row:** none — this number comes from the external CSV
  described above, not from Table 4.
- **Why it's needed:** without it, `sans_physiological_progression` stays
  unapproved and `simulation/physiological_generation.py` (per
  `evaluation/experiment_readiness.py`) keeps blocking every SANS detection
  metric — astronauts flagged with an event still get a flat/noisy trajectory
  with nothing to detect.
- **Options:**
  1. **Approve this exact rule** (slope = 0.04mm/day, linear, no cap) as a
     labeled synthetic design choice — explicitly not derived from the
     parameter sheet, explicitly from an external/unverified source.
  2. **Approve a capped version** — if you want a plateau, specify the cap
     value and the day/mechanism it kicks in; the CSV's tail is not strong
     enough evidence to choose one for you.
  3. **Reject this source entirely** and specify your own rule or say the
     capability stays blocked.
- **Type of approval required:** design decision
  (`registry/design_decisions.py::sans_physiological_progression`) — Rahat
  sets `approved=True`, `decision_text` (the exact chosen rule), and
  `approved_by="Rahat"`. No one else may set these fields.
- **Algorithm still missing:** yes, even after approval — implementing this
  in `simulation/physiological_generation.py` with deterministic tests is a
  separate step, done only once a rule is actually approved.
