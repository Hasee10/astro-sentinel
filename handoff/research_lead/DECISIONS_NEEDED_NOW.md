# Decisions Needed Now

Rewritten 2026-11-04 (ASTROSENTINEL correction, Part 6) after your 8 assumption
approvals + the trigger-firing decision unblocked `sweep_blockers()` - but a
follow-up correction found that an **open ground truth gap** (not an approval gap)
still blocks every real run: see item 1. This file is now organized around the 8
items you asked for specifically. Full technical detail for the generation-layer
items lives in `GENERATION_MODEL_SPECS.md`; the complete history of every question
(including the ones already resolved) is in `BLOCKER_QUESTIONS.md`.

**Already resolved, not repeated below:** trigger-firing method and swept values,
fixed-schedule interval (7 days), decision-tier thresholds (15/40/80%), ONSD
baseline/within-person SD, scan failure rate (10%, 50/50 split), the venous
Bayesian LR model and its flow-class likelihood ratios, SANS susceptibility/event
rates (75/25, 30/70). All eight are active in `registry/data/assumptions.json`
with `approved_by: "Rahat"`.

**Schedule context unchanged:** integrated build due Nov 6, experimental results
expected Nov 10-11. Every item below is now genuinely on the critical path - the
crossover experiment is correctly blocked by every one of them simultaneously,
confirmed by `evaluate_policies.py`'s own real output (run today: immediate
`evaluation_blockers.json`, zero CSV/PNG).

---

## 1. Event-onset timing distribution (highest priority - blocks everything else)

- **Exact missing rule:** which day within the 30-day mission a hidden SANS event
  (already flagged via the approved `has_sans_event`) actually starts.
- **Why necessary:** `has_sans_event=True` with `sans_onset_day=None` is the data
  state for every SANS-event astronaut today. A follow-up correction found
  `evaluate_policies.py` was silently scoring this as "0 missed events" - now
  fixed to refuse instead (`evaluation/experiment_readiness.py`), but that means
  **no real result can be produced until this is approved**, not just a less
  thorough one.
- **Blocks:** `evaluate_policies.py` entirely (both outcomes), via the new
  preflight readiness gate - confirmed blocking on every real run as of this
  correction.
- **What you must approve:** a concrete convention - e.g. a fixed day, or a day
  sampled from a declared range - via `registry/design_decisions.py::
  sans_venous_onset_day_assignment`. Still needs an implementation step after
  approval (see `GENERATION_MODEL_SPECS.md` item 7).

## 2. SANS physiological progression model

- **Exact missing rule:** how ONSD (and any other SANS-relevant measurement)
  actually changes, day by day, for an astronaut once their event has started.
- **Why necessary:** even once item 1 is resolved, every generated ONSD reading
  today is flat/noisy regardless of `has_sans_event` - there is no superimposed
  signal to detect. Resolving onset-day alone would let the experiment *run*; it
  would not let it *detect anything real*.
- **Blocks:** `simulation/physiological_generation.py::generate_onsd_scan()` for
  any non-healthy trajectory; meaningfully non-trivial detection-delay results.
- **What you must approve:** a progression shape (e.g. linear ramp over N days to
  a target magnitude) and its parameters. None proposed by this team - genuinely
  open.

## 3. Venous event prevalence, progression, and flow

- **Exact missing rule:** three things, all absent: (a) what fraction of
  astronauts actually get a venous event at all, (b) when, (c) how their jugular
  flow class/area changes once it starts.
- **Why necessary:** unlike SANS, there is **no approved event-occurrence model
  for venous at all** - today's `scenario_label` venous assignment is this
  project's own unprincipled 50/50 structural placeholder, not a scientific claim,
  and is never read as ground truth by the evaluator
  (`evaluation/experiment_readiness.py::venous_ground_truth_status` returns
  "undetermined" unconditionally). The venous Bayesian LR model you approved
  computes a correct probability *from a flow-class observation when one exists*
  - it says nothing about when or how often one should exist.
  - **Why this is three questions, not one:** approving a prevalence rate alone
    (mirroring SANS's 75/25 + 30/70) would still leave timing and progression
    open, exactly like SANS items 1-2.
- **Blocks:** `jugular_scan_values` generation entirely; all venous detection
  metrics, unconditionally, regardless of any other approval.
- **What you must approve:** an event-occurrence rate (or rates, by some
  analogous susceptibility split if you want one), an onset-timing rule, and a
  flow-class progression rule. None proposed - genuinely open, and the largest
  single gap remaining.

## 4. Maximum adaptive scan gap and deferral rules

- **Exact missing rule:** for the Option B replacement policy
  (`evaluation.policies.AdaptiveReplacementSchedulePolicy`, approved in principle
  only), the full set is: maximum permitted gap between scans, the lookback
  window for "fresh" trigger evidence (previously silently defaulted to 3 days -
  removed, now exactly as mandatory as the gap), mandatory-scan conditions (not
  implemented), failed-scan retry behavior (not implemented), and whether
  SANS/venous acquisition should be accounted separately (not implemented - also
  tangled with item 6 below).
- **Why necessary:** without these, this class cannot be instantiated at all
  (both `max_gap_days` and `defer_lookback_days` are required constructor
  arguments with no default) - and it must not be, since
  `adaptive_scheduling_policy_semantics` stays unapproved
  (`registry/design_decisions.py`).
- **Blocks:** any experiment claiming scan *savings* (Option A structurally
  cannot show this - see `DECISIONS_NEEDED_NOW.md`'s predecessor and
  `evaluation/policies.py::AdaptiveSchedulePolicy`'s docstring).
- **What you must approve:** concrete numbers/rules for all five sub-items above,
  together, as one design-decision sign-off.

## 5. Measurement acquisition and retry rules

- **Exact missing rule:** whether a scan that comes back degraded/failed (per the
  approved 10% failure rate) should trigger an earlier mandatory re-scan, and on
  what schedule; and whether SANS (ONSD) and venous (jugular) measurements may be
  acquired on the same day at all - the shared contract currently allows only one
  structured `scan` per astronaut-day.
- **Why necessary:** without a retry rule, a failed scan simply waits for the
  next anchor day, which may materially affect detection delay once items 1-2
  are resolved. The same-day question is a schema change, not a scientific
  value, and the only item in this document that would touch
  `handoff/frontend/CONTRACT_CHANGELOG.md`.
- **Blocks:** nothing today (both are currently moot while items 1-3 block
  everything), but will block a scientifically complete result once they're
  resolved.
- **What you must approve:** a retry rule (or confirm none is wanted), and a
  same-day-acquisition decision (keep one scan/day / add a second field / model
  scans as a list) - the first is a design decision, the second is a design
  decision with a schema-change consequence.

## 6. SANS evidence-to-posterior model (monitoring-layer, separate from item 2)

- **Exact missing rule:** a formula turning a real SANS measurement (once item 2
  exists) into an updated probability - the monitoring-layer counterpart to the
  venous Bayesian LR model you already approved.
- **Why this is NOT the same as `sans_prior_mapping`:** that approval authorizes
  the crew **generator's** synthetic susceptibility/event/time-prior scheme only
  (ground truth bookkeeping) - `monitoring/engine.py`'s
  `MONITORING_PROBABILITY_IMPLEMENTED = {"venous"}` deliberately does not include
  "sans", so `probability.sans` stays null unconditionally regardless of any
  approval touching generation. An earlier version of this correction batch
  briefly got this distinction wrong in code (not just documentation) before a
  test caught it.
- **Why necessary:** without this, SANS can never produce a real probability no
  matter what else is resolved.
- **Blocks:** `monitoring/engine.py`'s SANS branch, permanently, until approved.
- **What you must approve:** a prior/likelihood-ratio mapping and confirmation of
  which ONSD evidence feeds it. **Do not approve reusing the ICP likelihood
  ratios** (Koziarz/Ohle, original or revised) **for this** without a separately
  stated scientific justification - they remain explicitly scoped to ICP
  diagnosis only throughout the registry (see `onsd_accuracy_koziarz_2019` /
  `_rev1` and siblings).

## 7. HRV numerical values, if required for display

- **Exact missing rule:** actual HRV baseline/measurement values (not the
  trigger-firing model, which is separate and already approved and implemented).
- **Why necessary:** `daily_hrv_weak_signal` generation is explicitly forbidden
  from inventing a distribution (per your own instruction, preserved from the
  original correction), so `weak_signals.hrv_hf_power`/`hrv_lf_hf` stay null even
  though the trigger that conceptually stands in for HRV already works.
- **Blocks:** only a frontend/demo *display* of a numeric HRV value - the trigger
  mechanism itself does not need this and already works without it.
- **What you must approve:** confirm whether this is even wanted for the demo at
  all (a reasonable answer is "no" - the trigger flag can be shown instead), and
  if so, a sourced generation model.

## 8. Off-axis bias realization method

- **Exact missing rule:** you approved the off-axis positive-bias **range**
  (0.3-0.5mm); this project's own engineering choice of 0.4mm (the midpoint) as
  the deterministic operational value was never separately confirmed.
- **Why necessary:** a corrective review flagged that this specific sub-choice
  was being treated with the same confidence as the clearly-approved numbers
  around it (the 10% rate, the 50/50 split, the range itself). It has NOT been
  deactivated - it is the running value, stays within your approved range, and
  invents no distribution - but it now reads as explicitly pending in
  `registry/data/assumptions.json::onsd_scan_failure_rate.value_or_range
  .off_axis_positive_bias_mm.operational_value_status`.
- **Blocks:** nothing today (ONSD generation keeps running with this value) -
  this is a confidence-labeling fix, not a new block.
- **What you must approve:** confirm the midpoint (0.4mm), or specify the low
  end, high end, or a swept set instead.

---

## Dependency chain (unchanged mechanism, updated content)

```
item 1 (onset timing)  ──────────────┬──► evaluate_policies.py unblocks for SANS scan-count/trigger metrics only
item 2 (SANS progression) ───────────┤        (detection-delay/missed-events still need item 2 too, to have a
                                      │         real signal to detect, not just a schedulable day)
item 6 (SANS posterior model) ───────┴──► probability.sans ever non-null

item 3 (venous prevalence+timing+flow) ──► venous unblocks for ANY metric (currently blocked unconditionally)

item 4 (adaptive replacement rules) ─────► Option B usable; a scan-savings claim becomes possible

item 5 (retry / same-day acquisition) ───► refines items 1-3's results once they exist; blocks nothing by itself today

item 7 (HRV values) ──────────────────────► display only, blocks nothing mechanical

item 8 (off-axis bias method) ───────────► confidence/labeling only, blocks nothing
```

**The single highest-priority item remains item 1** - it is the one gap that, by
itself, keeps `evaluate_policies.py` fully blocked today regardless of everything
else already approved. Item 3 is the second-highest: venous is blocked
*unconditionally*, with no partial credit for any amount of SANS progress.
