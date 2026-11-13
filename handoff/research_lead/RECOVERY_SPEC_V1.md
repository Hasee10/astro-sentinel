# User relayed scientific implementation specification

Version: `user-relayed-2026-11-13-v1`. Status: **pending independent written
confirmation**. The machine-readable authority for the exact relayed values is
[`spec.json`](../../backend/research_v1/spec.json). It includes provenance and
every interpretation used by the engineering implementation. The approval sheet
is [`RECOVERY_APPROVAL_SHEET.md`](RECOVERY_APPROVAL_SHEET.md).

## Models and their provenance

| Model | Relayed specification and equation | Implementation | Verification |
|---|---|---|---|
| SANS occurrence | High susceptibility 25%; event probability high 70%, low 30%; separate purpose-specific RNG streams | `research_v1/physiology.py::make_case` | Independent outcome streams; no labels on observation contract |
| SANS onset | Uniform integer 5–20; demonstration day 8 | `make_case` | Demonstration onset and pre-onset plateau checked |
| Personal ONSD | Normal(5.35, 0.25) clipped to [4.8,5.9] mm | `make_case` | Personal baselines retained on measurements |
| SANS progression | A~Uniform[0.3,1.0] mm, R~integer Uniform[6,10]; B+A×clamp((d−onset)/R,0,1); demo A=0.6,R=10 | `latent` | Exact day-13 +0.3 mm and plateau +0.6 mm for day-8 demonstration |
| ONSD noise | Independent zero-mean Gaussian within-person SD 0.2 mm and observer SD 0.1 mm | `acquire` | Deterministic purpose/day/outcome streams; same-day values identical across policies |
| SANS evidence | ΔONSD≥0.3 mm → LR 7.2, otherwise 0.07; degraded readable log weight 0.2; unusable contributes none | `research_v1/monitoring.py::assess` | Hand-calculated Bayes, weighted poor evidence, unavailable-not-zero |
| SANS prior | P₀=5% or 10% explicit synthetic preflight input; +0.1 percentage point/day, cap25%; conflicts with historical generation-only +0.5 | `assess` | Day-dependent posterior calculation; old registry unchanged pending confirmation |
| Evidence decay | Latest log LR multiplied by 2^(−age/half-life); half-life7, sweep4/7/14 days | `assess` | Seven-day age halves log evidence; no daily LR multiplication |
| Venous event | Independent Bernoulli(0.30); integer uniform onset3–15; demo6 | `make_case` | Independence distribution check and separate onset streams |
| Jugular geometry | Baseline mean34 mm², SD20%; seven-day ramp toward multiplier Uniform[1.5,3], latent cap108 mm² | `latent` | Healthy/event/both trajectories, cap; positive-truncated Gaussian baseline is a pending interpretation |
| Flow | Antegrade before onset+2, then stagnant; half of event cases retrograde from onset+5; healthy false stagnant8%, retrograde2% | `latent` | Flow transition boundary checks; disjoint false-flow categories |
| Jugular noise | SD10% of latent area; Gaussian interpretation pending | `acquire` | Independent acquisition streams; area never used as disease LR |
| Venous monitoring | Prior5%, separate from event prevalence30%; LR antegrade0.3/stagnant4/retrograde10; decayed latest log LR | `assess` | Historical LR restriction retained; no sequential accumulation |
| Area flag | Area>1.2×personal baseline gives at least Repeat; no probability from area | `assess` | Flag separate from flow LR and measurement quality |
| Shared acquisition | One session attempts both outcomes, each independent 10% acquisition problem probability; one next-day full retry | `run.py::run_case` and `ScanSession` contract | Exactly two attempts/session; retry next day; shared count once |
| Fixed | Day1 anchor every7 days plus retries | `scheduling.py::decide` | Exact days1,8,15,22,29 when no retry required |
| Adaptive replacement | Day1, max-gap14, trigger lookback3, minimum trigger gap2, Repeat/Consult follow-up2, Urgent1, routine interval7 with deferral | `decide` | Different days from fixed; safety backstop, trigger and retry precedence; pending interpretations explicit |
| Trigger | Generator-side h=1−(1−s)^(1/5) on onset..onset+4; background0.05/day; s0.5–0.9 | `physiology.py::triggers` | Scheduler receives booleans, never onset; same random draws paired across sensitivity settings |
| Tiers | Independent15/40/80% simulation thresholds; red-flag override; no automatic Urgent clearance | `assess`, active `monitoring/engine.py` | Consult from hypothetical positive evidence; explicit red-flag Urgent; failure preserves serious alert |
| Consultation | Ten explicit states; separate delayed request and return transmission, manual synthetic review, immutable evidence packet | frontend `consultation.js` | Clock guards, snapshot immutability, ten-state unit and desktop/mobile browser checks |

All newer numerical models are **hypothetical synthetic research proposals
relayed by the user**. Existing 2026-11-04 repository approvals retain their
original scope. The primary-paper geometry correction is a literature observation,
not approval of a disease model. The external-CSV +0.04 mm/day function is not
called by this implementation.

## Measurement and policy boundary

Private `Case` stores events/onsets and latent physiology. A separate fictional
`PreflightInputs` carries only identity and the starting prior. `DayView` exposes
only the current day, previous session summaries, current tiers, retry due date,
and observed trigger dates. It rejects future trigger/session inputs. The monitor
accepts acquired chronological observation history and the preflight prior; it
does not accept `Case`. Potential measurements are generated deterministically
only when a policy requests the corresponding session. Observations contain no
hidden onset, susceptibility, event label or future measurement.

Monitoring uses the *latest readable evidence* with decayed log LR, a documented
engineering interpretation awaiting confirmation. This is especially important:
the old venous approval explicitly forbids multiplying correlated daily LRs.
Only observed, scheduled measurements can feed an assessment. Unusable scans do
not turn a previous serious alert into a low-risk result.

## Metrics

One session counts once regardless of two acquisition attempts. Successful,
degraded and failed measurements are counted separately; retry sessions are
identified. Detection is Repeat-or-higher **physiological** evidence with an
evidence day on or after the synthetic onset; quality-only Repeat never counts.
Mean delay is conditional on detected cases and always accompanies missed counts.
Healthy Consult/Urgent assessment-days and unique affected astronauts are both
reported, preserving `evaluation/metrics.py`'s mission convention.

Shared seeds/cases/measurements make policy comparisons paired. The three-seed,
five-sensitivity, three-half-life run produces 90 policy rows and 45 paired
differences. No validated crossover or performance claim follows from it while
the research gate remains closed.
