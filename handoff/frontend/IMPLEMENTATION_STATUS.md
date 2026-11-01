# Implementation Status

Legend: ✅ Implemented and tested · 🔶 Implemented but scientifically blocked · ⬜ Planned, not implemented.

| Capability | Status | Notes |
|---|---|---|
| Synthetic crew generation (structure, 30-day skeleton, scenario assignment) | ✅ | `generate_crew.py`, tested |
| Synthetic physiological measurement values | 🔶 | Every generative capability gated behind an unapproved assumption; see `simulation_manifest.json`'s `physiological_generation_blocked_reasons` |
| `assess_history()` monitoring function — rule-based tiers (red-flag→Urgent, degraded/failed quality→Repeat) | ✅ | Live, tested, SANS/venous independence verified |
| `assess_history()` — numeric probability calculation | 🔶 | Blocked on `sans_prior_mapping`, `venous_probability_model`, `decision_tier_thresholds` (all unapproved) |
| Batch scoring (`score_crew.py`), no-look-ahead guarantee | ✅ | Tested explicitly for leakage across days |
| Ground-truth / monitoring-visible data isolation | ✅ | Structural — `ObservableCase`/`ObservationMetadata` cannot carry hidden onset/scenario fields; regression-tested |
| Fixed-schedule policy | ✅ | Day-one anchoring convention fixed and tested across intervals/mission lengths |
| Adaptive-schedule policy | ✅ | Same anchoring + trigger-day union, tested |
| Adaptive-vs-fixed evaluation pipeline (`evaluate_policies.py`) | ✅ (code) / 🔶 (data) | Executes end-to-end and correctly refuses to fabricate a result; blocked today by 3 unapproved assumptions + 1 unregistered modeling gap |
| Trigger-accuracy sweep + crossover plot | ✅ (code) / 🔶 (data) | `evaluation/plotting.py` tested on engineering fixtures; real output requires the same unblock as above |
| Frontend JSON Schema export | ✅ | `schema/*.schema.json`, generated directly from the Pydantic models |
| Crew dashboard | ⬜ | Not in this team's scope — see §1 "Our team responsibilities" |
| Earth/ground dashboard, delayed-communication simulation | ⬜ | Not implemented; no live API exists |
| Mission playback | ⬜ | Not implemented |
| Authentication / live API server | ⬜ | Does not exist. The frontend consumes static JSON/JSONL files produced by the CLI scripts above — there is no running backend service to call. |

**Do not claim** any ⬜ or 🔶 item is complete in a demo or pitch deck without
reading this table first.
