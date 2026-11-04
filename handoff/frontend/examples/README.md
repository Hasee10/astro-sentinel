# Example data — what's real vs. engineering-only

All files here were produced by actually running the backend (nothing is hand-written
JSON) — the distinction below is about which **scenario** generated them, not
whether the JSON is genuine.

## Real pipeline output (from `generate_crew.py --seed 42 --crew-size 8` → `score_crew.py`)

- `example_observations_blocked.jsonl` — astronaut A1's full 30-day observation
  record. `weak_signals`/`scan` are null throughout: this is the honest current
  state (physiological generation is scientifically blocked), not a bug.
- `example_scored_blocked.jsonl` — A1's corresponding 30 `AssessmentResult` records.
  Every tier is `"unresolved"`, every probability `null` — again, the honest
  current state.
- `example_simulation_manifest.json`, `example_simulation_blockers.json`,
  `example_evaluation_blockers.json`, `example_scoring_summary.json` — real run
  metadata and blocker reports from the same run.

## Engineering fixtures — NOT simulation output, for UI-building only

- `example_engineering_fixture_observations.jsonl` /
  `example_engineering_fixture_scored.jsonl` — three hand-constructed observations
  (`astronaut_id` starts with `FIXTURE-`) that exercise the rule-based tiers the
  engine can produce *today*: a red-flag symptom (→ `urgent`), a scan explicitly
  marked `failed` quality (→ `repeat`), and an ONSD scan whose on-axis acquisition
  metadata was never recorded, so the engine itself derives an `"unknown"` quality
  status (→ also `repeat` — a quality-indeterminate scan is treated the same as a
  poor one). These exist only so the frontend developer has non-`unresolved`
  tier examples to build the Urgent/Repeat UI states against before real
  physiological simulation is unblocked. Each scored record's `tier_reason`
  field (v0.4.0+) shows exactly why — `red_flag_symptom` for the Urgent example,
  `measurement_quality` for both Repeat examples.
  **Never present these `FIXTURE-*` astronaut ids or their data as a real mission
  result in a demo.**
