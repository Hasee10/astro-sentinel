# Field Reference — Schema v0.4.0

Full machine-readable definitions are in `schema/*.schema.json` (exported directly
from the Pydantic models — always the source of truth; this document is a
human-readable companion, not a replacement).

## AstronautDayObservation (`crew_observations.jsonl`)

| Field | Type | Nullable | Unit | Meaning | Display guidance |
|---|---|---|---|---|---|
| `astronaut_id` | string | no | — | Synthetic crew member id (e.g. `"A1"`) | Label/select key |
| `day` | int | no | mission day (1-30) | Which day this record is for | X-axis / timeline position |
| `weak_signals.hrv_hf_power` | float | yes | dimensionless ratio | Daily cheap HRV signal | Only if non-null; currently always null (generation blocked) |
| `weak_signals.hrv_lf_hf` | float | yes | dimensionless ratio | Daily cheap HRV signal | Same |
| `weak_signals.ptt_ms` | float | yes | ms | Pulse transit time signal | Same |
| `scan.type` | enum | yes | — | `onsd` / `jugular` / `oct` / `visual_acuity` / `symptoms` | Which confirmatory measurement this record holds, if any |
| `scan.onsd_mm` | float | yes | mm | Optic nerve sheath diameter | SANS-relevant |
| `scan.jugular_area_mm2` | float | yes | mm² | Jugular cross-sectional area | Venous-relevant |
| `scan.jugular_flow_class` | string | yes | — | antegrade / stagnant / retrograde | Venous-relevant, qualitative only — never convert to a probability yourself |
| `scan.red_flag_symptom` | bool | yes | — | If true, Table 2 escalates the relevant outcome to Urgent unconditionally | Show as an alert banner, not folded into a probability bar |
| `scan.quality.status` | enum | no (on a scan) | — | `ok` / `degraded` / `failed` / `not_taken` / `unknown` (new in v0.3.0) | Degraded/failed/unknown all trigger `repeat` |
| `probability.sans` / `probability.venous` | float [0,1] | **usually yes** | — | Independent per-outcome probability | **Never 0 as a stand-in for null** — render "unavailable" |
| `tier.sans` / `tier.venous` | enum | no | — | `monitor`/`repeat`/`consult`/`urgent`/`unresolved` | See INTEGRATION_README §9 |
| `metadata.synthetic` | bool | no | — | Always `true` | — |
| `metadata.synthetic_label` | string | no | — | `"SYNTHETIC - NOT REAL ASTRONAUT DATA"` | **Must be shown somewhere on any screen displaying this data** |
| `metadata.run_id` | string | no | — | Which generation run this came from | Provenance |
| `metadata.schema_version` | string | no | — | `"0.4.0"` | Check before assuming field shape |
| `metadata.generation_blocked` | bool | no | — | True while physiological generation is blocked | Drives "why is this blank" messaging |
| `metadata.blocked_reasons` | list[string] | no | — | Capability ids blocking generation | — |
| `metadata.approved_assumptions_used` | list[string] | no | — | Which assumption ids were active for this run | Provenance only |

**Removed in v0.2.0 (breaking change):** `metadata.scenario_label` — see
`CONTRACT_CHANGELOG.md`. Do not expect this field; it will never return to a
monitoring-visible record.

**Added in v0.3.0 (additive, non-breaking):** `QualityStatus.UNKNOWN` — a scan
(currently only derived automatically for `scan.type == "onsd"`) whose on-axis
acquisition metadata was never recorded, so quality cannot be established either
way. Distinct from `not_taken` (no scan attempted). Treat it the same as
`degraded`/`failed` for display purposes (drives `repeat`).

## AssessmentResult (`crew_scored.jsonl`) — per outcome (`sans` / `venous`)

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `astronaut_id` | string | no | Same as above |
| `as_of_day` | int | no | The assessment is valid only using history through this day (no look-ahead) |
| `{sans,venous}.probability` | float | yes | Null today for every record — no approved model |
| `{sans,venous}.probability_label` | string | yes | Reserved for a future qualitative label (e.g. "elevated") once approved |
| `{sans,venous}.tier` | enum | no | See tier table in INTEGRATION_README §9 |
| `{sans,venous}.tier_reason` | enum | no | **New in v0.4.0.** `red_flag_symptom` / `measurement_quality` / `insufficient_evidence_for_probability` — WHY the tier was assigned, kept separate from the tier value itself. **A `repeat` with `tier_reason="measurement_quality"` is NOT evidence of a detected event — display this distinction, don't collapse it.** |
| `{sans,venous}.measurement_quality` | enum | yes | `ok`/`degraded`/`failed`/`unknown`, from the latest relevant scan |
| `{sans,venous}.evidence_references` | list[string] | no | Which parameter-sheet rule(s) back this tier (e.g. `onsd_measurement_protocol`) — good for a "why" tooltip |
| `{sans,venous}.limitations` | list[string] | no | Exactly which assumption id(s) are blocking a probability — **render this text when probability is null** |
| `{sans,venous}.explanation` | string | no | Full plain-English reasoning — good for an expandable "details" panel |

## SimulationManifest (`simulation_manifest.json`)

| Field | Meaning |
|---|---|
| `scenario_structure_generated` | Always `true` — the 30-day record skeleton and scenario-class assignment never needs blocked science |
| `physiological_values_generated` | `true` only once a real generation algorithm (not just an approved assumption value) exists and ran. **Always `false` as of this handoff.** |
| `physiological_generation_blocked_reasons` | capability → human-readable reason map |
| `generation_status` | `"fully_blocked"` / `"partially_blocked"` / `"complete"` — coarse summary; prefer the two fields above for anything more specific |

## ScoringSummary (`scoring_summary.json`)

| Field | Meaning |
|---|---|
| `errors` | Fatal per-record scoring failures (e.g. malformed history) — should be empty for valid input |
| `structural_warnings` | **New in v0.3.0.** Non-fatal structural inconsistencies in a source record (e.g. a scan with no quality metadata) — the record is still scored; this is a data-quality signal, not an error state |
| `sans_tier_distribution` / `venous_tier_distribution` | Count of each tier across all scored days, per outcome |

## Evaluation scan accounting (`adaptive_vs_fixed.csv`/`.json`, once unblocked)

Not part of `AstronautDayObservation`/`AssessmentResult` - these are
`evaluate_policies.py`'s own output columns, documented here only because the
frontend may eventually chart the comparison table once real values exist.

| Field | Meaning |
|---|---|
| `scans_used` | **Unchanged research metric** — count of days the policy decided a scan was due |
| `scans_with_data` | New in v0.4.0. Of those, how many days the underlying synthetic case actually had scan data |
| `scans_valid` | Of those, how many had `quality.status == "ok"` |
| `scans_degraded_or_unknown` | Of those, how many had degraded/failed/unknown quality |
| `scans_unavailable` | Requested, but no scan data existed at all — **today this equals `scans_used` for every row**, since physiological generation remains blocked; that is the honest current state, not a bug |

## Blocker reports (`simulation_blockers.json`, `evaluation_blockers.json`)

| Field | Meaning |
|---|---|
| `blockers[].capability` | What is unavailable |
| `blockers[].blocked_by` | Assumption id(s) that would need approval (empty list = a design decision with no registry slot yet, not a missing number) |
| `blockers[].message` | Human-readable reason — show this directly |
