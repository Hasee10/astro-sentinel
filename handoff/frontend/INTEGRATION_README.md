# Frontend Integration Guide — Autonomous Fluid-Shift Monitoring (Backend v0.2.0)

This package is everything the frontend developer needs to start building the crew
and Earth dashboards **without reading the backend's scientific source code**.

## 1. What the backend does

- Generates a synthetic (never real) astronaut crew mission dataset: 1 record per
  astronaut per day, for a 30-day mission.
- Scores each astronaut's chronological history day-by-day with one authoritative
  monitoring function, `assess_history()`, producing **two fully independent**
  outcomes per day: a SANS (neuro-ocular) assessment and a venous-stasis assessment.
- Runs an adaptive-vs-fixed measurement-scheduling comparison and a trigger-accuracy
  sweep, when the underlying scientific assumptions are approved (today, they are
  not — see §7 and §10).
- Every output is clearly labeled `SYNTHETIC - NOT REAL ASTRONAUT DATA` and every
  unsupported numeric value is `null`, never a fabricated number or a `0`.

## 2. What the backend does NOT do

- It does not diagnose, treat, or recommend any medical intervention. There is no
  medication, anticoagulation, or treatment field anywhere in this contract, and
  there will not be.
- It does not currently compute a numeric SANS or venous probability. All 14
  scientific/simulation assumptions behind those numbers are unapproved as of this
  handoff (§7). Until the research lead approves them, every probability field is
  `null` and every tier that would require one is `"unresolved"`.
- It does not combine SANS and venous into one score. There is no "overall risk"
  field, and the frontend must never compute or display one either.
- It does not provide a live API, Earth-communication delay simulation, or
  authentication. Those are future work (§9).

## 3. Which JSON files to consume

| File | Produced by | What it is |
|---|---|---|
| `crew_observations.jsonl` | `generate_crew.py` | One record per astronaut per day — raw monitoring input. **Monitoring-visible.** |
| `crew_scored.jsonl` | `score_crew.py` | One `AssessmentResult` per astronaut per day — the actual tiers/probabilities to display. **This is the main file the frontend renders.** |
| `ground_truth.jsonl` | `generate_crew.py` | Hidden scenario labels and onset days. **Evaluation-only — the frontend must NEVER read or display this file.** It exists so our own evaluation harness can score itself; showing it anywhere in a UI would be presenting the hidden answer key as if it were a real detection. |
| `simulation_manifest.json` | `generate_crew.py` | Run metadata: crew size, seed, which capabilities are blocked. Useful for a "run info" panel. |
| `simulation_blockers.json` / `evaluation_blockers.json` | `generate_crew.py` / `evaluate_policies.py` | Machine-readable reasons a capability is unavailable. Render these as the "why is this blank" explanation, not as an error. |
| `scoring_summary.json` | `score_crew.py` | Aggregate tier-distribution counts for a run — good for a summary panel. |
| `adaptive_vs_fixed.csv` / `.json`, `trigger_accuracy_sweep.csv`, `trigger_accuracy_crossover_*.png` | `evaluate_policies.py` | Only produced once the sweep is unblocked (not today — see §7). Do not expect these files until then. |

## 4. What each record represents

One `AstronautDayObservation` (in `crew_observations.jsonl`) = what was collected for
one astronaut on one mission day: optional daily "weak signal" readings
(`weak_signals`), an optional confirmatory `scan`, and provenance metadata. It never
contains a probability or tier — those are `score_crew.py`'s output.

One `AssessmentResult` (in `crew_scored.jsonl`) = the monitoring engine's judgment
for one astronaut **as of** one day, using only that astronaut's history up to and
including that day (no look-ahead). It has two independent sub-objects, `sans` and
`venous`, each with its own `tier`, `probability` (nullable), `explanation`, and
`limitations`.

## 5. How to run data generation

```bash
cd backend
python generate_crew.py --crew-size 8 --seed 42 --output-dir outputs/run1
```

For a byte-reproducible run (e.g. to regenerate the exact example data in this
package), pin both the run id and the timestamp:

```bash
python generate_crew.py --crew-size 8 --seed 42 --output-dir outputs/run1 \
  --run-id run-smoke-001 --created-at 2026-11-01T00:00:00+00:00
```

## 6. How to run scoring

```bash
python score_crew.py --input outputs/run1/crew_observations.jsonl --output-dir outputs/run1
```

## 7. Displaying the two independent monitoring outcomes

Always render SANS and venous as two separate panels/cards/trend lines. Never:
- Sum, average, or otherwise combine their probabilities or tiers into one score.
- Imply that one outcome's tier predicts or explains the other's.
- Display `ground_truth.jsonl`'s `scenario_label` or onset days anywhere a user
  (crew or Earth-side clinician) can see them — that file is the hidden answer key
  used only by our own evaluation code, never a monitoring output.

## 8. What a null probability means

`probability.sans` / `probability.venous` being `null` means **no scientifically
supportable calculation exists today** — not "zero risk" and not "pending." Every
`AssessmentResult`'s `sans.limitations` / `venous.limitations` array names the exact
unapproved assumption(s) blocking it (e.g. `sans_prior_mapping`). Display the
explanation text, not a fabricated percentage or a blank.

## 9. What each monitoring tier means

| Tier | Meaning | Source |
|---|---|---|
| `monitor` | Routine — no concern raised. Not currently reachable without an approved probability model; reserved for future use. | Table 2 |
| `repeat` | The latest relevant scan's quality was degraded or failed; it barely moved any estimate and should be retaken. | Table 2, rule-based, live today |
| `consult` | Would indicate a moderate concern warranting clinician review. Not currently reachable without an approved probability/threshold model. | Table 2 |
| `urgent` | A red-flag symptom was recorded on a scan. Escalates unconditionally, independent of any probability. | Table 2, rule-based, live today |
| `unresolved` | Explicit "insufficient evidence to decide" state — the honest default while probability calculation is blocked. **Not an error.** | This project's own convention — never silently substitute `monitor` for this. |

Today, only `repeat`, `urgent`, and `unresolved` are reachable; `monitor` and
`consult` require an approved probability/threshold model (§10 blocker list).

## 10. What to display when a calculation is blocked

Read the `limitations` array on the relevant `OutcomeAssessment`, or the
`blocked_reasons` / `blockers` array on the manifest / blocker-report files, and
show that text (or a short paraphrase) instead of the missing number — e.g. "SANS
probability unavailable: no approved prior/likelihood model yet." Never substitute
a placeholder number, a default tier, or hide the field.

## 11. Interface independence — what the frontend must NOT do

- Calculate a clinical probability, sensitivity/specificity figure, or any numeric
  risk score itself.
- Implement any prediction, scoring, or threshold logic — all of that belongs in
  `monitoring/engine.py` and is already independently tested.
- Invent a decision threshold, color-code boundary, or numeric cutoff that isn't
  already in the JSON (display thresholds for UI styling are fine; clinical
  thresholds are not).
- Generate any synthetic medical measurement.
- Read, display, or use `ground_truth.jsonl` (hidden scenario labels / onset days)
  in any user-facing view.
- Modify `backend/registry/data/*.json` (the scientific parameter/assumption
  source data).
- Calculate or reproduce the adaptive-vs-fixed crossover value itself — consume
  `adaptive_vs_fixed.json`/`.csv` and the rendered PNG once they exist.

The frontend's job is strictly to consume and display backend output.

## 12. Validating output against the schema

```bash
python -c "
import json, jsonschema
schema = json.load(open('../handoff/frontend/schema/assessment_result.schema.json'))
record = json.loads(open('outputs/run1/crew_scored.jsonl').readline())
jsonschema.validate(record, schema)
print('valid')
"
```

(`jsonschema` is a common Node/Python package; any JSON Schema Draft 2020-12
validator in your frontend's own language/toolchain works identically.)

## 13. Running the backend test suite

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q
```

Expect `142 passed` as of this handoff (78 scientific-registry tests + 64 new tests
covering the generator, monitoring engine, scheduling, evaluation metrics, sweep,
plotting, and CLI integration).
