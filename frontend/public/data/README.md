# Frontend data files

The app loads its data from these two folders. Keep real backend output and mock
data apart, so nobody mistakes one for the other.

## `pipeline/`: real backend output

These are copied from a backend run, usually `backend/outputs/<run>/`. To show a new
run, overwrite the files with that run's versions, and keep all of them from the same
run.

| File | Copied from |
|---|---|
| `crew_scored.jsonl` | `backend/outputs/<run>/` |
| `crew_observations.jsonl` | `backend/outputs/<run>/` |
| `simulation_manifest.json` | `backend/outputs/<run>/` |
| `scoring_summary.json` | `backend/outputs/<run>/` |
| `simulation_blockers.json` | `backend/outputs/<run>/` |
| `evaluation_blockers.json` | `backend/outputs/<run>/eval/` |

The app appears in the file dropdown as "Backend pipeline run (schema v0.6.0)". It
shows a warning if the data reports any other schema version.

## `fixtures/`: mock and old example data

None of this is current backend output. These files come from
`handoff/frontend/examples/`.

| File | What it is |
|---|---|
| `example_engineering_fixture_scored.jsonl` | Hand-constructed records for building the UI. Shown as "MOCK – engineering fixture, not backend output", always with the purple warning. Never present it as a mission result. |
| `example_scored_blocked.jsonl` | Pipeline output for one astronaut from an earlier, blocked run on an older schema. Shown as "OLD EXAMPLE – earlier blocked run, not current backend output". |
| `example_simulation_manifest.json` | The manifest from that earlier run. |

## Never put these here

**`ground_truth.jsonl` must never be put in `public/data/` or any folder inside it.**
It holds the hidden answers used to evaluate the backend, and the frontend must never
read or display it. Everything in `public/` is copied into the build and can be
opened by URL, including this README.

Don't add `experiment_readiness_summary.json` either, because it reports counts taken
from the ground truth.

Note that `pipeline/evaluation_blockers.json` also quotes ground-truth counts in its
message text. The app removes them before showing a message, but the raw file can
still be opened by URL.
