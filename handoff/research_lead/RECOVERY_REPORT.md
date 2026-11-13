# AstroSentinel recovery report

The authorized engineering and operator-workflow repairs are implemented. The
full research experiment is **not approved for activation or deployment**. New
scientific specifications are user-relayed; evidence aggregation and scheduling
interpretations still require independent written confirmation. The complete
chain executes in explicitly labeled engineering mode, without presenting its
metrics as validated experiment results.

The complete changed-file list is [RECOVERY_CHANGED_FILES.json](RECOVERY_CHANGED_FILES.json).

## Audit and checkpoint

Local main was one commit behind remote. A recoverable Git bundle was saved at
`D:/astro-sentinel-before-recovery.bundle`, then main was fast-forwarded to
`b43ce8c78bf30d4531a0b0094b60da48c3d9db0e`. A subsequent remote fetch found no
concurrent commits. No new permanent branch, force push, remote push or deployment
was performed. Both source DOCX files and vn.txt remain unchanged.

Inspected contracts, simulation, monitoring, evaluation, registry, tests, CLI
runners, publishing, frontend presentation/experience, research handoffs, all
public JSON/JSONL/manifests, and both original mission DOCX files. Google Drive
search returned no newer AstroSentinel approval file. The attachment contained
the request, not separate deployed screenshot files. The described UI failures
were reproduced locally and checked in desktop/mobile browsers.

## Dependency map and root causes

| Causal step / problem | Root cause in latest main | Recovery and remaining boundary |
|---|---|---|
| Synthetic occurrence | SANS sampling exists; venous occurrence absent | Gated independent outcome sampling in research_v1/physiology.py |
| Onset and progression | No approved onset; active ONSD is baseline/noise; no jugular generation | Capped SANS and venous ramps implemented behind research gate |
| SANS probability | Generation-only prior was expected to imply a monitoring formula, which does not exist | Gated baseline-relative LR model; production nulls remain honest |
| Venous probability | Approved latest-flow LR formula has no generated flow input | Active model preserved; gated actual jugular area/flow generation |
| Prior conflict | Historical +0.5 pp/day versus relayed +0.1 pp/day | Both scopes documented; +0.1 used only behind gate |
| Reference discrepancy | Both briefs transcribe supine area108 | Registry corrected to103 from primary paper; synthetic108 cap stays separately pending |
| Available observations | Daily candidate values published as actual scans | Production fixed-anchor acquisition projection; unused candidates private |
| Scan scheduling | Old adaptive includes every fixed scan; replacement incomplete | Gated causal replacement scheduler with explicit retry/trigger/deferral precedence |
| Quality and tiers | Technical Repeat dominates; failed scan could overwrite serious evidence | Separate quality, evidence, probability and action; serious alerts survive inadequate scans |
| Next action | Frontend used generic review text | Structured backend action codes, evidence day and follow-up state rendered consistently |
| Consultation | Snapshot/ack transport without medical-review workflow | Ten-state synthetic delayed request/review/response/acknowledgment |
| Evaluation | Missing science correctly blocks scoring | Production remains blocked; actual 90-row engineering comparison executes separately |
| Records | Pagination hid selected later-day evidence | Selected day determines initial page; event jump opens matching Records |
| Timeline | Primarily ONSD/tier changes | Dual traces, sessions, triggers, deferrals, tier changes, consultation events |
| Research | Sparse readiness workspace | Explicit Results tab states approval restrictions without fabricated charts |
| Privacy | Old fixture manifest exposed scenario-count aggregate | Removed; recursive check now covers every public fixture and manifest |
| Shared-session leakage | Legacy evaluator originally masked only scan | Both acquisition representations are policy-masked; bounded prior-session view and regression test |

The production causal chain still stops at unconfirmed onset/progression and
monitoring authorization. The legacy +0.04 mm/day external-CSV function remains
gated and is not called by the recovery model.

## Models and approval sources

Already recorded Rahat-attributed approvals are preserved: susceptibility25/75,
SANS occurrence70/30, baseline Normal(5.35,0.25) clipped4.8–5.9 mm, within-person
SD0.2 mm, historical scan artifacts, seven-day fixed anchor, synthetic15/40/80%
tiers, five-day trigger mechanism/5% background/0.5–0.9 sweep, and venous prior5%
with latest-flow LRs0.3/4/10. Their original scopes remain intact.

New relayed rules implemented but not independently signed include onset
distributions, amplitudes/ramps, observer noise, SANS LRs, +0.1 prior supersession,
decayed weighted evidence, venous occurrence/geometry/flow/noise, shared retries,
and adaptive replacement precedence. Equations, values, provenance, code and
tests are mapped in [RECOVERY_SPEC_V1.md](RECOVERY_SPEC_V1.md). Exact questions
are in [RECOVERY_APPROVAL_SHEET.md](RECOVERY_APPROVAL_SHEET.md).

Lee et al. report103 mm² (95% CI75–131) for supine1g. This corrects reference
geometry, not a disease threshold or the relayed synthetic108 mm² cap. Both
original DOCX files retain their historical108 transcription. Source:
[Lee et al.2020, Results](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2020.00863/full).

## Recomputed data

The original published run exactly reproduced the old counts:300 profiles,
30 days,9,000 records,9,000 unavailable probabilities per outcome,977
quality-related SANS Repeat assessments, zero Consult/Urgent and zero jugular
measurements. Every day carried a candidate ONSD scan.

The regenerated **production fixed-policy demo** retains9,000 daily records but
has only1,500 scheduled sessions:1,342 good,81 degraded and77 failed ONSD
measurements. SANS has931 Repeat and8,069 Unresolved assessment-days; venous has
9,000 Unresolved. Probabilities remain unavailable. A quality issue can persist
between acquisitions: assessment counts are not scan counts. No unconfirmed
retry protocol is silently activated in this dataset.

The separate five-profile **engineering acceptance dataset** has78 shared
sessions,156 measurements,141 good,6 degraded and9 failed. It exercises all four
tiers and contains actual ONSD/jugular acquisitions. It is not a representative
cohort. Exact counts are in [RECOVERY_VERIFICATION.json](RECOVERY_VERIFICATION.json).

## Actual engineering trajectories

Hidden scenario explanation belongs in this separated research report. Public
profile IDs do not encode hidden conditions or onset.

| Profile | Construction | Actual behavior |
|---|---|---|
| E1 | No events | Sessions1,3,6,20,23,26,27,29; Monitor with occasional technical/false-flow Repeat; healthy truth does not force perfect observations |
| E2 | SANS onset8, amplitude0.6 mm over10 days | Acquired sessions reveal baseline-relative change and physiological Repeat independently of quality |
| E3 | Venous onset6 | Jugular area rises; flow changes after onset+2 and potentially onset+5; SANS remains independently assessed |
| E4 | Both demonstration events | Day14 good ONSD6.120 mm yields SANS47.84%, Consult; simultaneous jugular58.67 mm² and retrograde flow yield venous34.48%, Repeat. Day20 degraded acquisition does not clear prior Consult |
| E5 | Explicit day1 red-flag acceptance input | Urgent on day1, daily adaptive follow-up; no randomly invented red-flag incidence and no automatic clearance |

Historical venous flow LRs yield approximately1.55%,17.39%,34.48% from prior5%.
These observations alone cannot reach40% Consult. No numbers were inflated to
manufacture a venous Consult/Urgent example. Separate explicit test inputs verify
higher-tier precedence and the sourced red-flag override.

## Actual engineering comparison

**Not validated experiment results.** The gated run uses60 profiles per seed,
seeds42/43/44, five trigger settings0.5–0.9 and half-lives4/7/14 days:90 policy
rows and45 paired differences, all labeled `validated_for_experiment=false`.

At trigger0.7 and half-life7, pooling180 synthetic cases across the three seeds:

| Metric | Fixed | Adaptive replacement |
|---|---:|---:|
| Shared sessions including retries |1,068|1,579|
| Retry sessions |168|240|
| Good / degraded / failed measurements |1,923 /109 /104|2,828 /181 /149|
| SANS detected / total events |66/68|59/68|
| SANS mean delay among detected cases |7.41 days|6.08 days|
| SANS missed events |2|9|
| SANS false Consult/Urgent assessment-days |12|19|
| Venous detected / total events |59/59|59/59|
| Venous mean delay among detected cases |4.76 days|4.49 days|
| Venous missed events / false-escalation days |0 /0|0 /0|

Adaptive uses511 more sessions, misses seven more SANS events and produces seven
more false-escalation days here. Shorter delay among detected cases does not
establish a better overall trade-off. No validated crossover claim is made.
Full seed/outcome results, tier distributions and paired differences are in
[RECOVERY_ENGINEERING_RESULTS.json](RECOVERY_ENGINEERING_RESULTS.json).

One shared session counts once. Technical quality Repeat does not count as
physiological detection. Detection requires supporting evidence acquired on or
after onset. Mean delay is conditional on detected cases and accompanies missed
counts. False-escalation days and unique affected healthy astronauts are separate,
preserving the mission convention in evaluation/metrics.py.

## Consultation and frontend

Ten states are recorded: suggested,requested,queued,sent,delivered,review-pending,
response-prepared,response-sent,response-received,closed. Each transmission leg
enforces its selected delay. Earth sees no packet before delivery; crew sees no
response before its return. Requests include profile/day/outcome, reason/tier,
relevant actual observation, follow-up and an immutable evidence snapshot.
Closing communication never clears an alert. Review is explicitly synthetic and
operator-driven, with no real doctor, external send or treatment recommendation.
State persists across workspace tabs during the browser session, not reloads.

Measurements distinguish current acquisition from last-recorded/last-good values,
with baselines and units. Event jumps reveal matching record pages. Consultation
controls work on mobile independently of the desktop sidebar. Existing dark
aerospace styling is preserved. Desktop/mobile records, charts and consultation
screenshots were inspected under frontend/test-results.

## Acceptance and deployment status

Acceptance tests cover healthy,SANS,venous,both; technical Repeat,physiological
Consult,explicit red-flag Urgent; next-day retry/shared counts; policy-dependent
scan days; reproducible metrics; delayed consultation; chart/record agreement;
future/hidden-information boundaries; and public data privacy. Detailed command
results are in [RECOVERY_TEST_RESULTS.md](RECOVERY_TEST_RESULTS.md).

Before Vercel: obtain written confirmation and resolve interpretation questions;
reconcile active registry approvals; integrate the confirmed runner into normal
evaluation/publication; execute the full approved study with required additional
threshold/noise/LR/failure/comparator sensitivity axes and uncertainty analysis;
publish validated comparison artifacts with provenance; rerun safety/function/
browser checks on a preview. Existing deployment is preserved.

The production experiment is still blocked. A green build is not completion of
the scientific research objective.
