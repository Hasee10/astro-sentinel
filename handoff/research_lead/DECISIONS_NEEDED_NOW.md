# Decisions Needed Now

A short, prioritized list of the minimum decisions needed to unblock a
scientifically executable crossover experiment. You should be able to answer
every question here without reading any backend source code. Full detail and
justification for each is in `BLOCKER_QUESTIONS.md` (same folder); technical
specs for the generation-layer items are in `GENERATION_MODEL_SPECS.md` — this
file does not repeat their content, only summarizes what's still needed and in
what order.

**Schedule context:** frontend data handoff was due Nov 3 (done — see
`handoff/frontend/`). Integrated build is due Nov 6. Experimental results are
expected Nov 10-11.

**Important:** approving a decision is necessary but not sufficient. Every item
below marked "Algorithm still missing: yes" also needs a backend implementation
step after your approval before it does anything — approving a value does not
by itself make a number appear (see the dependency chain at the bottom).

---

## 1. The trigger-firing simulation method (blocks EVERYTHING in deliverable 3)

- **Exact missing input/rule:** a method translating an assumed trigger
  accuracy/usefulness value (e.g. 0.7) into which specific days a synthetic
  trigger fires for a given case.
- **Parameter-sheet row:** none — simulation-design choice, no Table 4 entry.
- **Why the experiment requires it:** this is the one gap that blocks the
  crossover regardless of what else gets approved (checked unconditionally in
  `evaluation/sweep.py::sweep_blockers()`).
- **Available design choices:**
  1. Sensitivity/specificity model — trigger fires probabilistically based on a
     (sensitivity, specificity) pair against the hidden onset day.
  2. Fixed lead-time model — trigger always fires exactly N days before onset
     (N derived from the accuracy value), plus an independent false-positive rate.
  3. Your own alternative.
- **Expected effect on outputs:** determines how early/often adaptive scans
  relative to fixed across the swept accuracy axis — directly shapes the
  crossover curve's shape.
- **Approval type:** design decision (`registry/design_decisions.py`) for the
  *method*, **plus** experimental assumption (`hrv_trigger_assumed_accuracy`)
  for the swept *values*.
- **Algorithm still missing:** **yes.** Even after you approve a method, it
  must still be implemented to match the restricted `PolicyDayView` input
  contract (Phase 10) and pass dedicated tests before
  `TRIGGER_FIRING_MODEL_IMPLEMENTED` may be set to `True`.

## 2. Adaptive scheduling policy semantics (changes what the experiment can claim)

- **Exact missing input/rule:** whether the adaptive policy may ever use
  *fewer* scans than fixed, or only ever add extras.
- **Parameter-sheet row:** none — engineering/experimental-design choice.
- **Why the experiment requires it:** the currently-implemented policy is
  "fixed backstop + triggered extras" — it cannot, by construction, show a scan
  *saving*, only earlier detection for more scans. If your research question
  includes scan savings, this policy cannot answer it.
- **Available design choices:**
  - **A (already built):** fixed backstop + triggered extra scans.
  - **B:** defer/replace fixed scans based on evidence — can reduce scans, but
    needs you to also specify a maximum allowed gap between scans and a safety
    rule for when deferral isn't allowed.
  - **C:** a fixed scan budget reallocated to more informative days.
- **Expected effect on outputs:** changes whether "scans used" can ever favor
  adaptive in the comparison table — Option A structurally cannot; B/C could.
- **Approval type:** design decision.
- **Algorithm still missing:** no for Option A (already implemented and
  tested); **yes** for B or C.

## 3. Fixed-schedule interval

- **Exact missing input/rule:** the comparator interval in days.
- **Parameter-sheet row:** none — your brief's "every 7 days" is explicitly an
  example, not a chosen value.
- **Why the experiment requires it:** `evaluate_policies.py` cannot run
  without a declared comparator interval.
- **Available design choices:** any positive integer number of days.
- **Expected effect on outputs:** sets the fixed policy's baseline scan count
  and detection-delay floor that adaptive is compared against.
- **Approval type:** experimental assumption (`fixed_schedule_interval_choice`, numerical).
- **Algorithm still missing:** no — `FixedSchedulePolicy`/`AdaptiveSchedulePolicy`
  already implement the day-one-anchored interval correctly; this only needs a number.

## 4. Decision-tier probability thresholds

- **Exact missing input/rule:** the probability cutoffs separating
  Monitor/Repeat/Consult/Urgent, per outcome.
- **Parameter-sheet row:** none — Table 2 names the tiers, not numeric cutoffs.
- **Why the experiment requires it:** needed to turn any future probability
  into a tier at all; also one of the three assumptions `sweep_blockers()`
  unconditionally requires.
- **Available design choices:** threshold value(s) per outcome; may be swept
  like the HRV accuracy values rather than fixed.
- **Expected effect on outputs:** directly determines detection delay/missed
  events/false escalations once a real probability model exists.
- **Approval type:** experimental assumption (`decision_tier_thresholds`, numerical).
- **Algorithm still missing:** not applicable yet — this is only usable once a
  probability model (item not on this list; see `BLOCKER_QUESTIONS.md` items
  3-4) exists to threshold in the first place.

## 5. Sticky-Urgent / red-flag clearance rule

- **Exact missing input/rule:** whether/how an Urgent tier ever clears once a
  red flag has occurred.
- **Parameter-sheet row:** none — clinical-process design decision.
- **Why the experiment requires it:** today, once any red flag appears, that
  outcome stays Urgent for the rest of the mission — this will make every
  affected synthetic astronaut look "stuck" in any demo or evaluation table,
  and could distort missed-event/detection-delay metrics once real event data exists.
- **Available design choices:** never clear automatically (today's default) /
  clear after N consecutive clean scans (specify N) / clear only via an
  explicit synthetic "resolved" flag (specify how it's set) / your own rule.
- **Expected effect on outputs:** changes long-run tier distributions and any
  "percent of mission spent Urgent" style reporting.
- **Approval type:** design decision.
- **Algorithm still missing:** yes, if you want anything other than the
  current sticky default (which is already implemented).

## 6. Simultaneous SANS + venous measurement on one day — schema question (new)

- **Exact missing input/rule:** the shared contract currently allows exactly
  ONE structured `scan` per astronaut-day, with one `type` (ONSD/jugular/etc.).
  We verified the evaluator does NOT cross-count a scan into the wrong
  outcome's accounting (a venous/jugular scan is never counted as a SANS
  measurement or vice versa) — that was checked and is correct. But the
  schema itself cannot represent "both an ONSD scan AND a jugular scan on the
  same day" without a contract change.
- **Parameter-sheet row:** not applicable — this is a data-contract design
  question, not a scientific value.
- **Why the experiment requires it:** only if your research design assumes
  astronauts get simultaneous SANS and venous confirmatory measurements on the
  same day. If same-day measurements of both types are never required, there
  is nothing to change.
- **Available design choices:** keep one scan per day (current, no change) /
  add a second optional scan field for the other outcome / model multiple
  scans per day as a list.
- **Expected effect on outputs:** a schema change here is the ONE item in this
  document that would require touching the frontend-facing contract
  (`handoff/frontend/CONTRACT_CHANGELOG.md`) — we have not made this change
  and will not without your answer.
- **Approval type:** design decision (not scientific).
- **Algorithm still missing:** not applicable until you decide whether a
  change is even wanted.

---

## Implementation dependency chain

Which approvals unlock which backend components, in order:

```
hrv_trigger_assumed_accuracy (values)  ┐
trigger-firing method (decision)        ├──► trigger algorithm implemented ──► TRIGGER_FIRING_MODEL_IMPLEMENTED=True
                                         ┘         │
fixed_schedule_interval_choice ─────────────────────┤
decision_tier_thresholds ───────────────────────────┤
                                                     ▼
                                    evaluation/sweep.py::sweep_blockers() returns []
                                                     │
                                                     ▼
                              evaluate_policies.py produces a REAL adaptive_vs_fixed.csv/.json
                                          and trigger_accuracy_crossover_*.png
```

Separately, and NOT required for the above to run (the experiment can execute
with every probability still `null`):

```
sans_prior_mapping + venous_probability_model + onsd_baseline_sd_values + ...
          (see BLOCKER_QUESTIONS.md items 2-4, GENERATION_MODEL_SPECS.md)
                                   │
                                   ▼
          real (non-null) physiological values and probabilities
```

In other words: **items 1, 3, and 4 above are the minimum for
`evaluate_policies.py` to execute at all and produce a genuine (non-fabricated)
CSV/JSON/PNG instead of a blocker report.** Be aware this alone would still be
a scientifically thin result: with physiological generation and event-onset
assignment both still blocked (see `BLOCKER_QUESTIONS.md`), every synthetic
astronaut's scan and onset data stays null, so detection delay and missed
events would have nothing real to measure - the plot would show scan-count
differences between the two policies, honestly computed, but not yet a
clinically meaningful detection comparison. Item 2 decides which policy that
plot represents. Item 5 affects long-run tier reporting. Item 6 only matters
if you want same-day dual measurements. A scientifically substantive crossover
additionally needs the physiological-generation and onset-assignment items in
`BLOCKER_QUESTIONS.md`/`GENERATION_MODEL_SPECS.md`.

Everything else (SANS prior, venous probability model, personal ONSD
baselines, HRV/PTT weak-signal generation, jugular measurements, scan failure
rate) still matters for a scientifically complete result, but is not on this
milestone's critical path — see `BLOCKER_QUESTIONS.md` for the complete
prioritized list.
