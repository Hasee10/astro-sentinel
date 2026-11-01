# Field Reference — Schema v0.2.0

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
| `scan.quality.status` | enum | no (on a scan) | — | `ok` / `degraded` / `failed` / `not_taken` | Degraded/failed triggers `repeat` |
| `probability.sans` / `probability.venous` | float [0,1] | **usually yes** | — | Independent per-outcome probability | **Never 0 as a stand-in for null** — render "unavailable" |
| `tier.sans` / `tier.venous` | enum | no | — | `monitor`/`repeat`/`consult`/`urgent`/`unresolved` | See INTEGRATION_README §9 |
| `metadata.synthetic` | bool | no | — | Always `true` | — |
| `metadata.synthetic_label` | string | no | — | `"SYNTHETIC - NOT REAL ASTRONAUT DATA"` | **Must be shown somewhere on any screen displaying this data** |
| `metadata.run_id` | string | no | — | Which generation run this came from | Provenance |
| `metadata.schema_version` | string | no | — | `"0.2.0"` | Check before assuming field shape |
| `metadata.generation_blocked` | bool | no | — | True while physiological generation is blocked | Drives "why is this blank" messaging |
| `metadata.blocked_reasons` | list[string] | no | — | Capability ids blocking generation | — |
| `metadata.approved_assumptions_used` | list[string] | no | — | Which assumption ids were active for this run | Provenance only |

**Removed in v0.2.0 (breaking change):** `metadata.scenario_label` — see
`CONTRACT_CHANGELOG.md`. Do not expect this field; it will never return to a
monitoring-visible record.

## AssessmentResult (`crew_scored.jsonl`) — per outcome (`sans` / `venous`)

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `astronaut_id` | string | no | Same as above |
| `as_of_day` | int | no | The assessment is valid only using history through this day (no look-ahead) |
| `{sans,venous}.probability` | float | yes | Null today for every record — no approved model |
| `{sans,venous}.probability_label` | string | yes | Reserved for a future qualitative label (e.g. "elevated") once approved |
| `{sans,venous}.tier` | enum | no | See tier table in INTEGRATION_README §9 |
| `{sans,venous}.measurement_quality` | enum | yes | `ok`/`degraded`/`failed`, from the latest relevant scan |
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

## Blocker reports (`simulation_blockers.json`, `evaluation_blockers.json`)

| Field | Meaning |
|---|---|
| `blockers[].capability` | What is unavailable |
| `blockers[].blocked_by` | Assumption id(s) that would need approval (empty list = a design decision with no registry slot yet, not a missing number) |
| `blockers[].message` | Human-readable reason — show this directly |
