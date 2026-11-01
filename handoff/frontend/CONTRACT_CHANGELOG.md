# Contract Changelog

## v0.2.0 (this handoff, Unified Prompt 4-5 corrective milestone) — BREAKING

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
