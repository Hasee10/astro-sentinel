# Contract Changelog

## v0.4.0 (this handoff, Unified Prompt 8-9) — additive, non-breaking

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
