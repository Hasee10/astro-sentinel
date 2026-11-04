# Contract Changelog

## v0.6.0 (ASTROSENTINEL correction, 2026-11-04 cont'd) — additive, non-breaking

A corrective pass found that `evaluate_policies.py` was producing CSV/PNG output
from ground truth with an unresolved gap (`has_sans_event=True` with
`sans_onset_day=None`), silently reading as "0 missed events" instead of "unknown".
**No `AstronautDayObservation` or `AssessmentResult` field changed** - the fix lives
entirely in the evaluation layer and the manifest. Frontend code that only reads
`crew_observations.jsonl`/`crew_scored.jsonl` is unaffected; code that reads
`evaluate_policies.py`'s output or `simulation_manifest.json` should note:

- **`evaluate_policies.py` now writes `evaluation_blockers.json` far more often** -
  in practice, every run against current real data, because `has_sans_event=True`
  astronauts always have `sans_onset_day=None` today (onset-day assignment is
  unapproved) and no venous event-occurrence model exists at all yet. **This is
  correct, not a regression** - the prior behavior (producing CSV/PNG output from
  this data) was the defect. See `evaluation/experiment_readiness.py`.
- **Added** `evaluation_blockers.json`-adjacent `experiment_readiness_summary.json`
  on a blocked run - a per-outcome ground-truth status-count breakdown
  (`confirmed_none` / `confirmed_with_onset` / `event_unknown_onset` /
  `undetermined`), for debugging why a run was blocked beyond the blocker message text.
- **Added** `SimulationManifest.capability_readiness` - one of
  `simulation.generation_models.ModelReadiness`'s five states per generator
  capability, for the full picture `physiological_generation_blocked_reasons`
  alone didn't give (which only lists the blocked ones, not the ready ones).
- **Fixed** `SimulationManifest.generation_status`: previously read `"fully_blocked"`
  even when 3/7 generator capabilities were genuinely producing real values - now
  correctly reports `"partially_blocked"` in that case. `"fully_blocked"` and
  `"complete"` keep their original meanings exactly.
- `metadata.schema_version` on new records now reads `"0.6.0"`.

## v0.5.0 (ASTROSENTINEL, 2026-11-04) — additive, non-breaking

This is the milestone the "Not yet changed" note at the bottom of this file was
waiting for: Rahat approved 8/14 assumptions + the trigger-firing design decision,
and `probability.venous` now genuinely goes non-null in real output.

- **`probability.venous` is now sometimes non-null** in `crew_scored.jsonl`, via an
  approved Bayesian prior-odds x likelihood-ratio model keyed on the latest
  `scan.jugular_flow_class` observation. **Always check
  `AssessmentResult.venous.probability_label`** — it reads exactly
  `"Simulation placeholder - unvalidated"` whenever `probability` is set, and the
  frontend must display that label prominently alongside any shown number, never
  the bare percentage alone. `probability.sans` is still always null — approving
  `sans_prior_mapping` authorized a generation-layer synthetic scheme only, not a
  monitoring-layer formula (see `GroundTruthRecord` changes below).
- **Added** `TierReason.PROBABILITY_THRESHOLD` — a tier derived from an actual
  computed probability against `decision_tier_thresholds`, always paired with the
  `probability_label` above. Existing frontend code that switches on `TierReason`
  should add a case for this value rather than falling through to a default.
- **Added** three fields to `GroundTruthRecord` (`ground_truth.jsonl` — evaluation-
  only, same as `scenario_label`/`sans_onset_day`; **never send this file or its
  contents to any UI the crew or ground would see**): `is_sans_high_susceptibility`
  (bool), `has_sans_event` (bool), `synthetic_sans_prior_label` (str, always
  `"HYPOTHETICAL SIMULATION ESTIMATE - NOT CLINICALLY VALIDATED"` when present).
  These back the crew generator's own synthetic ground-truth bookkeeping only; they
  are not, and must never be treated as, a real SANS probability or diagnosis.
- **`scan.onsd_mm` is now sometimes non-null** in `crew_observations.jsonl` (ONSD
  baseline + daily drift + ~10% synthetic failure injection are approved and
  implemented). `scan.quality` is always populated alongside it. No jugular/OCT/
  visual-acuity scan is generated yet - `weak_signals` is still always null.
- **No field was removed or renamed.** `metadata.schema_version` on new records
  now reads `"0.5.0"`.

## v0.4.0 (Unified Prompt 8-9) — additive, non-breaking

- **Added** `TierReason` enum (`red_flag_symptom` / `measurement_quality` /
  `insufficient_evidence_for_probability`) and a new required field
  `{sans,venous}.tier_reason` on every `AssessmentResult` record
  (`crew_scored.jsonl`). This is WHY a tier was assigned, kept structurally
  separate from the tier itself - a `repeat` tier caused by poor scan quality
  must never be read as evidence a physiological event was detected. **Any
  frontend code that parses `crew_scored.jsonl` records should read this new
  field when deciding how to phrase a Repeat/Urgent explanation**, rather than
  inferring the reason from `explanation`'s free text.
- **Added** `ScanAccounting` (`requested` / `data_available` / `valid` /
  `degraded_or_unknown` / `unavailable`) on evaluation output only (not on
  `AstronautDayObservation` or `AssessmentResult` - this is an
  `evaluate_policies.py` CSV/JSON addition, not a per-observation field). The
  legacy `scans_used` research metric is **unchanged** in meaning.
  See `evaluate_policies.py`'s `adaptive_vs_fixed.csv`/`.json` new columns:
  `scans_with_data`, `scans_valid`, `scans_degraded_or_unknown`,
  `scans_unavailable`.
- **No field was removed or renamed** from `AstronautDayObservation`
  (`astronaut_id`, `day`, `weak_signals`, `scan`, `probability`, `tier`,
  `metadata` are all unchanged).

## v0.3.0 (Unified Prompt 6-7) — additive, non-breaking

- **Added** `QualityStatus.UNKNOWN` — a scan whose documented protocol metadata
  (currently: ONSD on-axis acquisition) was never recorded, so quality cannot be
  established either way. Distinct from `not_taken`. Existing consumers that only
  handle `ok`/`degraded`/`failed`/`not_taken` are unaffected unless they assume
  that list is exhaustive; treat `unknown` the same as `degraded`/`failed` for
  display (it drives `repeat`, same as those two).
- **Added** `monitoring/measurement_quality.py`: `derive_onsd_quality()` now fills
  in a missing ONSD scan's quality automatically from its `on_axis` field (an
  already-existing field — no new input required from the generator or frontend).
  An explicitly-set `quality` is never overridden.
- **Added** `scoring_summary.json`'s `structural_warnings` field (non-fatal
  structural-consistency flags, separate from `errors`).
- **No field was removed or renamed.** `metadata.schema_version` on new records
  now reads `"0.3.0"`.

## v0.2.0 (Unified Prompt 4-5 corrective milestone) — BREAKING

- **Removed** `ObservationMetadata.scenario_label` from every monitoring-visible
  `AstronautDayObservation`. This was a ground-truth-leakage defect (Defect 1 of
  the corrective review): a hidden scenario identity must never be readable from a
  record the monitoring engine, scheduler, or frontend can see. Scenario label and
  onset-day information now live **exclusively** on `GroundTruthRecord`
  (`ground_truth.jsonl`), which the frontend must never read.
  - **Migration:** if any frontend code reads `metadata.scenario_label`, delete it.
    There is no replacement field — this information is intentionally no longer
    monitoring-visible.
- **Added** `SimulationManifest.scenario_structure_generated`,
  `physiological_values_generated`, and `physiological_generation_blocked_reasons`
  (Defect 2: an approved numeric assumption does not by itself mean a generation
  algorithm exists — the manifest now says so explicitly instead of only exposing
  the coarser `generation_status` string).
- **Added** `generate_crew()`/`generate_crew.py --created-at` for deterministic
  replay (Defect 8) — does not change any output field, just makes exact
  reproduction possible.

## v0.1.0 (original Unified Prompt 4-5 build)

- Initial shared contract: `AstronautDayObservation`, `GroundTruthRecord`,
  `SimulationManifest`, `Blocker`/`BlockerReport`, independent `OutcomeProbability`/
  `OutcomeTier` nested objects per the mission document's illustrative sketch.

## Not yet changed, but tracked as likely future versions

- `AssessmentResult` (the monitoring engine's output schema) has not changed shape
  in this milestone, only in what values it can legally contain (Defect 5/6 fixed
  the *evaluation* layer around it, not its own fields).
- Any future approval of a numeric assumption that lets `probability.sans` /
  `probability.venous` become non-null will **not** be a breaking change on its
  own (the field already exists and is already nullable) — but will be called out
  here with the run/assumption id so the frontend can confirm when real numbers
  start appearing.
