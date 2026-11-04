# Research-Lead Blocker Questions — Unified Prompt 4-5 (updated for Unified Prompts 6-7 and 8-9)

Generated from a direct read of `backend/registry/data/assumptions.json` (all 14
entries) plus two gaps the registry has no slot for at all (items 7 and 8/9 below).
Every item below blocks a specific, named backend capability. Nothing below has been
assigned a value by the backend team — each needs your explicit answer. No prior
answer or blocker in this document has been removed or altered by the Unified
Prompt 6-7 or 8-9 updates — only new framing and new sections (items 10-14) were
added. **If you only have time to read one file, read
`DECISIONS_NEEDED_NOW.md` instead — it's the short, prioritized version of just
items 11, 12, and 14 below plus the trigger-firing-model decision (items 8-9).**

Priority follows your stated order: first data delivery (Nov 3) → physiological
trajectories → starting probabilities → venous model → tier thresholds → fixed
interval → HRV trigger behavior → sweep → crossover.

**Unified Prompt 6-7 update:** every blocker below is now also backed by a formal,
machine-checkable readiness state (`READY` / `BLOCKED_MISSING_PARAMETER` /
`BLOCKED_UNAPPROVED_ASSUMPTION` / `UNSUPPORTED_SCIENTIFIC_USE` /
`BLOCKED_MISSING_MODEL_RULE`) in `backend/simulation/generation_models.py`. See
`GENERATION_MODEL_SPECS.md` in this same folder for the full approval-ready
technical spec (inputs, parameters, output fields/units, expected verification
tests) behind each generation-layer item below (2, 3, 4, 6, 7, and the
`trigger_firing_simulation_model` half of 8-9). Items 1, 3, 4, 5 (SANS prior,
venous model, tier thresholds, fixed interval) are monitoring/evaluation-layer
decisions, not generation-layer ones, and are not duplicated there.

---

## 1. First-data-delivery blocker (target: Nov 3, 2026)

**Status: none of the items below are required for Nov 3.** The frontend handoff
package (`handoff/frontend/`) ships real, schema-valid, honestly-null data today —
no assumption approval is needed to unblock the frontend developer starting work.
If you intended "first data" to mean non-null physiological values, see item 2.

---

## 2. Synthetic physiological trajectories

- **Parameter-sheet row:** no single row — this spans
  `onsd_healthy_baseline_range`, `onsd_baseline_spread_assumption`
  (assumption: `onsd_baseline_sd_values`).
- **Missing:** a within-person ONSD standard deviation (or between-astronaut
  spread SD) to generate synthetic personal baselines and daily noise.
- **Why needed:** without it, `simulation/generator.py` cannot produce a single
  non-null ONSD value anywhere.
- **Blocked component:** `simulation/generator.py` → `personal_onsd_baseline_values`,
  `onsd_scan_values`.
- **Decision type:** experimental assumption (numerical) — the source document
  itself says this must be "set by lead" and swept, not fixed to one number.
- **Question:** What SD value(s) (or range to sweep) should we use to generate
  synthetic ONSD baselines and drift? Note: even once you approve a value, our
  team still has to **write and test the generation algorithm itself** — approving
  a number does not retroactively create working code (Defect 2 of this review).
  Flag which you want prioritized first.

- **Secondary row:** `onsd_technical_artifacts`, `onsd_measurement_protocol`
  (assumption: `onsd_scan_failure_rate`).
- **Missing:** a numeric rate at which synthetic scans should come back degraded/
  failed.
- **Question:** What fraction of synthetic scans should fail or degrade, and by
  which artifact type(s)?

---

## 3. Starting probabilities (SANS prior)

- **Parameter-sheet row:** `onsd_healthy_baseline_range`,
  `onsd_baseline_spread_assumption` (assumption: `sans_prior_mapping`).
- **Missing:** a formula mapping pre-flight inputs (baseline ONSD, optic cup size,
  dural sinus asymmetry) to a numeric starting SANS probability.
- **Why needed:** without this, every SANS probability stays `null` forever,
  regardless of what else is approved.
- **Blocked component:** `monitoring/engine.py`'s `sans` outcome, permanently
  (`PROBABILITY_BLOCKERS["sans"]`).
- **Decision type:** needs source verification — "optic cup size" and "dural sinus
  asymmetry" appear in your mission brief's prose but have **no numeric row in
  Table 4 at all**. The brief's own 5% figure is explicitly labeled a placeholder,
  not a derived value.
- **Question:** Is there a primary source for a cup-size/asymmetry → prior mapping
  you want us to use, or should we proceed with a synthetic-only placeholder
  explicitly labeled as such (and if so, what value), or should this prior simply
  stay unavailable for the hackathon demo?

---

## 4. Venous-stasis monitoring model

- **Parameter-sheet row:** `jugular_stasis_prevalence_iss`,
  `jugular_csa_by_gravity_level`, `jugular_area_velocity_cutoffs`,
  `jugular_ultrasound_measures_inflight` (assumption: `venous_probability_model`,
  a **scope decision**, not a number).
- **Missing:** a decision on whether venous monitoring should ever emit a
  numeric probability at all, versus staying qualitative (flow class,
  collapsibility, days persistent) forever.
- **Why this is a scope decision, not a number request:** there is **no**
  sensitivity/specificity/likelihood-ratio data for any jugular ultrasound measure
  anywhere in your parameter sheet. The registry's own recommended default is
  "stay qualitative" — we are not asking you to invent a number, we are asking you
  to confirm that default or override it with a sourced method.
- **Blocked component:** `monitoring/engine.py`'s `venous` outcome, permanently
  until this is answered either way.
- **Question:** Confirm venous stays qualitative-only for this hackathon (our
  recommended default), or provide a sourced method for a numeric venous
  probability.

- **Related:** `jugular_flow_risk_mapping` (numerical) — a mapping from jugular
  area/flow class to a risk flag/level. Blocked for the same reason (no numeric
  cutoff exists in any cited source per `jugular_area_velocity_cutoffs`).
  **Question:** if you want any risk-flag signal before the full probability
  model, what flow-class → flag mapping should we sweep?

---

## 5. Decision-tier threshold rules

- **Parameter-sheet row:** none — Table 2 names the four tiers
  (Monitor/Repeat/Consult/Urgent) but gives no numeric probability cutoff between
  them (assumption: `decision_tier_thresholds`).
- **Why needed:** even if items 3-4 were resolved, we still could not turn a
  probability into a tier without this.
- **Blocked component:** `monitoring/engine.py`, both outcomes
  (`TIER_THRESHOLD_BLOCKERS`); `evaluation/sweep.py` (metrics key off tiers).
- **Decision type:** experimental assumption (numerical) — your own instruction is
  that any future value here is simulation-only and must be swept, never
  presented as a clinical cutoff.
- **Question:** What probability threshold(s) separate Monitor/Repeat/Consult/
  Urgent, for each outcome independently? Should these be swept across a range
  (as with the HRV accuracy) rather than fixed?

---

## 6. Fixed scheduling interval

- **Parameter-sheet row:** none — your mission brief's "one measurement every 7
  days" is explicitly an *example*, not a chosen value (assumption:
  `fixed_schedule_interval_choice`).
- **Why needed:** `evaluate_policies.py` cannot run the adaptive-vs-fixed
  comparison without a declared comparator interval.
- **Blocked component:** `evaluation/sweep.py::sweep_blockers()`,
  `evaluate_policies.py`.
- **Decision type:** team design choice, explicitly required to be a declared
  decision per your own brief ("the team picks the fixed schedule and states it"),
  not a value we infer.
- **Question:** What interval (in days) should the fixed-schedule comparator use?
  Note: we already fixed a day-one anchoring bug in the scheduler itself (Defect
  6) — a 7-day interval now correctly produces days 1, 8, 15, 22, 29, not the old
  1, 7, 14, 21, 28.

---

## 7. HRV trigger simulation behavior

- **Parameter-sheet row:** `hrv_onsd_coefficient`, `hrv_confounders`
  (assumption: `hrv_trigger_assumed_accuracy`).
- **Missing:** the swept accuracy values themselves (the brief's own illustrative
  points are 50%, 60%, 70%+) **and** a rule for translating an assumed accuracy
  into which specific days a synthetic trigger fires.
- **Why this is two separate gaps:** approving a list of accuracy values to sweep
  (e.g. `[0.5, 0.6, 0.7, 0.8, 0.9]`) does **not** by itself tell us which days a
  trigger with "70% accuracy" should fire on for a given synthetic case. That
  translation has no proposed method anywhere in the source and is a new,
  unregistered gap — see item 9.
- **Blocked component:** `simulation/generator.py`'s `daily_hrv_weak_signal`;
  `evaluation/sweep.py`'s entire sweep axis.
- **Question (a):** What list/range of assumed accuracy values should we sweep?
- **Question (b):** See item 9 below — we need your sign-off on a firing-behavior
  rule before question (a)'s values can do anything.

- **Related, lower priority:** `ptt_trigger_assumed_usefulness` — PTT isn't even
  in Table 4 (only named in prose) as a "lower priority than HRV" secondary
  modifier. **Question:** confirm PTT stays out of scope for this hackathon, or
  provide a source.

---

## 8 & 9. Trigger-accuracy sweep and crossover calculations

- **The actual blocking gap (new, not yet in the registry):** `evaluation/sweep.py`
  unconditionally reports a blocker named `trigger_firing_simulation_model` with
  `blocked_by: []` — meaning **there is no assumption id for this at all**, because
  it is a simulation-design choice, not a parameter-sheet value. We have not
  silently added one or guessed a rule, per your explicit instruction.
- **Why this is the one that actually matters most:** even if every other
  assumption above were approved today, the crossover experiment would **still**
  be fully blocked by this single gap, because nothing currently defines how
  "assumed trigger accuracy = 0.7" becomes a specific set of simulated trigger-fire
  days for a specific synthetic case.
- **Blocked component:** `evaluation/sweep.py::sweep_blockers()` — unconditionally,
  every single run, until this changes.
- **Decision needed from you (not a number — a method):** pick one of (or propose
  your own):
  1. **Sensitivity/specificity model** — treat "accuracy" as a
     (sensitivity, specificity) pair against the hidden onset day, and have the
     trigger fire probabilistically day-by-day based on those two numbers.
  2. **Fixed lead-time model** — the trigger always fires exactly N days before
     the hidden onset (with N a function of the accuracy value), with some
     independent false-positive rate elsewhere.
  3. **Something else** you specify.
  Whichever you choose, we also need confirmation that "accuracy" here is **not**
  the same thing as classification sensitivity/specificity/overall accuracy
  unless you explicitly say so — your mission brief and our own contracts
  deliberately avoid conflating "diagnostic performance," "trigger usefulness,"
  and "scheduling-decision accuracy," and we will not merge them without your
  sign-off.
- **Once this is answered**, items 5-7 above (tier thresholds, fixed interval,
  HRV accuracy sweep values) are the remaining prerequisites for a real,
  non-fabricated crossover plot — `evaluate_policies.py` and
  `evaluation/plotting.py` are already built, tested on engineering fixtures, and
  wired to run the instant `sweep_blockers()` returns empty.

---

## Lower-priority items (not in your 9-point list, included for completeness)

- `onsd_icu_cutoff_reuse_scope` (scope decision): may the 5.0mm ICU/ICP cutoff be
  reused as a *soft trend marker* in SANS monitoring at all? The source labels
  reuse itself as the open question, separate from the cutoff's value.
- `onsd_interobserver_noise_magnitude` (numerical): no numeric magnitude exists in
  the cited source (Ballantyne et al. 2002) for inter-observer scan noise.
- `sans_cnn_reuse_scope` (scope decision): may the SANS-CNN sensitivity/
  specificity/F1 figures stand in for an external OCT-classification step's
  reliability? This is our own proposed interpretation, not stated in your brief
  — needs explicit sign-off either way.
- `evidence_atlas_lr_reliance` (scope decision): the pooled ONSD likelihood-ratio
  figure is self-labeled "Established (weak source)" pending locating its
  original meta-analysis — may we use it at all before that's found, and at what
  weight relative to the three named primary studies?
- `communication_delay_exact_value` (numerical): the 0-20 minute Earth-delay range
  is itself marked "Confirm," not yet confirmed — not currently relevant to the
  backend's scope but flagged for whoever builds the Earth dashboard.

---

## 10. Measurement quality — nothing to approve, for awareness only

Unified Prompt 6-7 added `monitoring/measurement_quality.py`, which derives an
ONSD scan's quality status automatically from its existing `on_axis` field (an
already-sourced protocol requirement — `onsd_measurement_protocol`/
`onsd_technical_artifacts`, both "Established" in Table 4). This needed **no new
approval**: it only reads a field the contract already had, and introduces no new
number. A new quality state, `unknown` (scan quality indeterminate because on-axis
metadata was never recorded), was added to the schema for this — additive, not
breaking, documented in `handoff/frontend/CONTRACT_CHANGELOG.md`. This item exists
only so you're aware of the change; there is no decision for you to make here. The
*randomized* failure-injection capability (item 6, `onsd_scan_failure_rate`) is a
separate, still-genuinely-blocked capability — don't conflate the two.

---

## 11. Adaptive scheduling policy semantics (new, Unified Prompt 8-9) — needs your decision

An independent code review found that the currently-implemented adaptive policy
is exactly **"fixed backstop + triggered extra scans"**: it always performs every
fixed-schedule scan, and may add more when a trigger fires. By construction, its
scan count can never be lower than the fixed policy's for the same interval (we
added a test proving this: `test_adaptive_can_never_schedule_fewer_scans_than_fixed`).

This is not a bug, but it means the current implementation **cannot, by design,
demonstrate "adaptive scheduling uses fewer scans"** - only "detects sooner for
more scans." If your research question is about scan *savings*, not just earlier
detection, the current policy cannot answer it.

- **Decision type:** design decision (not a parameter-sheet value) — this governs
  *what we build*, not a scientific input.
- **Why we need the answer:** which policy we implement materially changes what
  the crossover plot can and cannot claim.
- **Options** (full detail: `DECISIONS_NEEDED_NOW.md`):
  - **A (current):** fixed backstop + triggered extras. Simple, safe, cannot save scans.
  - **B:** defer/replace fixed scans based on evidence — can reduce scans, but
    needs explicit maximum-scan-gap and safety rules before we'd implement it.
  - **C:** a fixed scan *budget* reallocated to more informative days.
- We have **not** implemented B or C — they need your sign-off first, since they
  change the experiment's meaning, not just its code.

## 12. Requested vs. completed scan accounting (new, Unified Prompt 8-9) — convention pending

The evaluation previously counted every *requested* scan as if it were a
completed measurement. We've now separated "requested" from "data available",
"valid (quality OK)", "degraded/unknown quality", and "unavailable" (see
`evaluate_policies.py`'s new CSV columns). The legacy `scans_used` metric's
*meaning* is unchanged (still "requested") — we did not redefine it without
telling you.

- **Decision needed:** once physiological generation is unblocked, should the
  research metric "scans used" continue to mean *requested*, or should it switch
  to counting only *valid completed* measurements? We have not chosen for you;
  today, since generation is blocked, `scans_unavailable` equals `scans_used` for
  every row — an honest reflection of current reality, not a defect.

## 13. Policy-specific scan visibility — already fixed, no decision needed

A serious experimental-validity bug was found and fixed this milestone: the
monitoring engine could previously see a scan recorded in a case's underlying
data on a day the policy being evaluated never actually scheduled a scan (e.g. a
scan on day 6 was visible to the fixed policy's day-8 assessment, even though the
fixed policy never requested day 6). This is now structurally prevented —
`ObservableCase.visible_history()` masks out any scan the specific policy run
didn't request, for both fixed and adaptive, over the same underlying cohort.
Regression tests added. **No action needed from you** — flagged here only so
you're aware the fix exists, since it affects every future numerical experiment
result's validity.

## 14. Sticky Urgent / red-flag clearance rule (new, Unified Prompt 8-9) — needs your decision

Current rule: once ANY day in an astronaut's history carries a red-flag symptom,
every later day's assessment for that outcome stays Urgent forever - there is no
implemented clearance, reset, or resolution rule.

- **Decision type:** engineering/clinical-process design decision - not a
  parameter-sheet numeric value, but it does need clinical judgment.
- **Why we need the answer:** without an approved resolution rule, every
  synthetic astronaut who ever triggers one red flag will show Urgent for the
  rest of the mission in any demo or evaluation output - this could look like a
  software bug if not explained, and could also distort evaluation metrics
  (e.g. "missed event" / "detection delay" calculations) once real event data exists.
- **Question:** should Urgent ever clear automatically (e.g. after N consecutive
  clean scans), only via an explicit synthetic "resolved" flag, or never (stay
  conservative/sticky forever, which is today's default)? We will not invent an
  automatic clearance rule without your sign-off.
