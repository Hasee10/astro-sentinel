# Generation Model Specifications (section 3.7, Unified Prompt 6-7; updated Unified Prompt 8-9)

Approval-ready technical specs for every currently-blocked physiological generation
capability, generated directly from `backend/simulation/generation_models.py`
(`GENERATION_MODEL_SPECS` — that module is the source of truth; this document is a
human-readable companion). Each spec names exactly what's required, what's missing,
and the precise decision needed from you — nothing here assigns or suggests a value.

**Readiness states** (`ModelReadiness`, section 3.6 — engineering states, never
medical diagnoses):

| State | Meaning |
|---|---|
| `READY` | Every required parameter exists, every required assumption is approved, and a tested generation algorithm exists in code. |
| `BLOCKED_MISSING_PARAMETER` | A referenced Scientific Parameter Registry id doesn't exist. |
| `BLOCKED_UNAPPROVED_ASSUMPTION` | A required NUMERICAL assumption is not yet approved with a value. |
| `UNSUPPORTED_SCIENTIFIC_USE` | A required SCOPE_DECISION assumption is not yet approved — the *use itself* isn't sanctioned, independent of any number. |
| `BLOCKED_MISSING_MODEL_RULE` | Either no generation algorithm is implemented yet, or (for the two unregistered gaps below) its `registry/design_decisions.py` entry is not yet approved. |

As of this handoff, **every capability below is blocked** — none is `READY`.

**Unified Prompt 8-9 update:** items 7 and 8 below (the two capabilities with no
Experimental Assumption slot) are now backed by an explicit
`registry/design_decisions.py::DesignDecision` entry instead of being
permanently, unconditionally blocked in code. Each clears only once BOTH its
decision is approved (a human edits that file - never code) AND its algorithm
is implemented (tracked next to `IMPLEMENTED_GENERATION_ALGORITHMS`). This
means a future approval does not require a developer to come back and delete a
hardcoded block.

---

## 1. `personal_onsd_baseline_values`
- **State:** `BLOCKED_UNAPPROVED_ASSUMPTION`
- **Required parameters:** `onsd_baseline_spread_assumption`, `onsd_healthy_baseline_range`
- **Required assumption:** `onsd_baseline_sd_values` (unapproved)
- **Output:** per-astronaut synthetic ONSD baseline (day 1), mm
- **Verification tests expected:** baseline within the healthy range for every astronaut; spread matches the approved SD within sampling tolerance; reproducible for a fixed seed
- **Decision needed:** approve a numeric SD (or range to sweep)

## 2. `onsd_scan_values`
- **State:** `BLOCKED_UNAPPROVED_ASSUMPTION`
- **Required parameters:** same as #1
- **Required assumption:** `onsd_baseline_sd_values` (unapproved)
- **Output:** daily ONSD reading drifting from baseline, mm
- **Verification tests expected:** no scenario-correlated drift for a healthy astronaut; no SANS/venous cross-correlation; values stay in-range
- **Decision needed:** same SD approval as #1, **plus** (separately, monitoring-layer) a progression rule before any non-flat trajectory may be generated for a non-healthy scenario

## 3. `daily_hrv_weak_signal`
- **State:** `BLOCKED_UNAPPROVED_ASSUMPTION`
- **Required parameters:** `hrv_onsd_coefficient`, `hrv_confounders`
- **Required assumption:** `hrv_trigger_assumed_accuracy` (unapproved)
- **Output:** `weak_signals.hrv_hf_power`, `weak_signals.hrv_lf_hf`, dimensionless
- **Verification tests expected:** generated signal never literally encodes the hidden onset day; sweeping the accuracy value changes evaluation-layer behavior, not the signal's raw shape
- **Decision needed:** the swept accuracy value list/range, **plus** (see #8 below) the firing-behavior translation rule

## 4. `daily_ptt_weak_signal`
- **State:** `BLOCKED_UNAPPROVED_ASSUMPTION`
- **Required parameters:** none (PTT has no Table 4 row at all)
- **Required assumption:** `ptt_trigger_assumed_usefulness` (unapproved)
- **Output:** `weak_signals.ptt_ms`, ms
- **Verification tests expected:** N/A until scope is confirmed
- **Decision needed:** confirm PTT is even in scope for this hackathon before further spec work

## 5. `jugular_scan_values`
- **State:** `UNSUPPORTED_SCIENTIFIC_USE` (the scope decision, not the number, is what's currently blocking — this spec needs BOTH resolved)
- **Required parameters:** `jugular_csa_by_gravity_level`, `jugular_area_velocity_cutoffs`, `jugular_ultrasound_measures_inflight`
- **Required assumptions:** `jugular_flow_risk_mapping` (numerical, unapproved) **and** `venous_probability_model` (scope decision, unapproved)
- **Output:** `scan.jugular_area_mm2`, `scan.jugular_flow_class`, `scan.jugular_collapsibility_lost`
- **Verification tests expected:** generated flow class stays within the qualitative categories the source actually names; no numeric venous probability is derived without `venous_probability_model` separately sanctioning it
- **Decision needed:** confirm `venous_probability_model`'s scope decision (qualitative-only vs. numeric) first, then approve `jugular_flow_risk_mapping`'s numeric mapping if a risk-flag signal is wanted

## 6. `measurement_quality_failure_injection`
- **State:** `BLOCKED_UNAPPROVED_ASSUMPTION`
- **Required parameters:** `onsd_technical_artifacts`, `onsd_measurement_protocol`
- **Required assumption:** `onsd_scan_failure_rate` (unapproved)
- **Output:** `scan.quality.status`, `scan.quality.reasons`
- **Note:** distinct from the already-implemented, no-approval-needed deterministic on-axis rule in `monitoring/measurement_quality.py::derive_onsd_quality()` — that one only reads a scan's own `on_axis` field, it never randomly injects failures
- **Verification tests expected:** observed failure rate matches the approved rate within sampling tolerance; independent of scenario label
- **Decision needed:** approve a numeric synthetic scan failure rate

## 7. `sans_venous_onset_day_assignment` — no Experimental Assumption slot; tracked as a design decision
- **State:** `BLOCKED_MISSING_MODEL_RULE` — `registry/design_decisions.py::DESIGN_DECISIONS["sans_venous_onset_day_assignment"]` is unapproved
- **Required parameters / assumptions:** none registered
- **Output:** `ground_truth.sans_onset_day`, `ground_truth.venous_onset_day`
- **Verification tests expected:** deterministic given the seed; identical onset-day distribution across scenario classes sharing the same rule (no accidental difficulty tilt)
- **Decision needed:** propose and approve a convention — e.g. a fixed day, or a day sampled from a declared range/distribution. Once approved there, it still needs an implemented algorithm before this capability can report `READY`.

## 8. `trigger_firing_simulation_model` — no Experimental Assumption slot; tracked as a design decision; highest priority
- **State:** `BLOCKED_MISSING_MODEL_RULE` — `registry/design_decisions.py::DESIGN_DECISIONS["trigger_firing_simulation_model"]` is unapproved
- **Required parameters / assumptions:** none registered
- **Output:** boolean — whether the adaptive scheduler's trigger fires on a given day
- **Why this one matters most:** this single gap blocks the crossover experiment regardless of what else above gets approved (see `evaluation/sweep.py::sweep_blockers()`, which checks both the decision's approval AND `TRIGGER_FIRING_MODEL_IMPLEMENTED`)
- **Verification tests expected:** firing behavior never reads the hidden onset day through any path other than the explicitly-approved model itself; "accuracy" is never silently conflated with classifier sensitivity/specificity unless you say so explicitly
- **Decision needed:** choose and approve a method — see `DECISIONS_NEEDED_NOW.md` and `BLOCKER_QUESTIONS.md` items 8-9 for the three concrete options proposed. Approving the decision alone still does not unblock this - the algorithm then needs to be implemented and `TRIGGER_FIRING_MODEL_IMPLEMENTED` flipped to `True`.

---

Regenerate this document (if the specs change) with:

```bash
cd backend
python -c "
from registry.loader import load_all
from simulation.generation_models import GENERATION_MODEL_SPECS, check_readiness
registry = load_all()
for name, spec in GENERATION_MODEL_SPECS.items():
    result = check_readiness(spec, registry)
    print(name, '->', result.state.value, result.reasons)
"
```
