# Recovery verification results

Verification date: 2026-11-13. Baseline before changes: 297 backend tests passed.

| Command / check | Final result |
|---|---|
| `cd backend; python -m pytest -q` | 316 passed |
| `cd frontend; npm test` | 8 passed |
| `npm run check:data` | 9,000 production observations and matching assessments; all public fixtures/manifests checked recursively; no hidden keys |
| `npm run lint` | Passed |
| `npm run build` | Passed; production bundle generated |
| `npm run test:e2e` | 6 passed: three scenarios each in desktop and mobile-sized Chromium |
| Original DOCX/vn integrity tests | Passed as part of full backend suite |
| Schema snapshot synchronization | Passed as part of full backend suite |
| Real generation and scoring | 300 profiles, 30 days; 1,500 fixed-anchor sessions; outputs inspected |
| Normal full policy evaluator | Correctly blocked, including explicit replacement request; no fabricated comparison CSV/PNG |
| Gated engineering study | 90 real computed policy rows, three seeds, five trigger settings and three decay half-lives; not validated for experiment |
| Reproducibility | Paired same-day measurements and duplicate seeded study outputs agree |
| Git diff whitespace check | Passed |

The browser suite checks values against actual loaded records, selected-day
pagination, dual measurement display and jugular plotting, a physiological Consult
case, the delayed ten-state consultation including both transmission legs, the
Urgent acceptance case, and exact research-gate visibility. It checks page errors
and horizontal overflow in the main scenarios. Screenshots were inspected for
desktop/mobile records, charts and consultation. Mobile emulation uses an iPhone
13 viewport in Chromium; native iOS Safari and the existing live Vercel deployment
were not tested.

## Acceptance case mapping

| Requested case | Evidence |
|---|---|
| A Healthy | Latent healthy trajectory test and E1 acceptance profile; good quality is not equated with perfect health |
| B SANS progression | Exact capped ramp arithmetic and E2/E4 observable measurements |
| C Venous progression | Area/flow boundary tests and E3/E4 actual jugular acquisitions |
| D Both | Independent dual-condition construction and E4 paired measurements |
| E Technical Repeat | Weighted/failed quality tests; structured technical-reacquisition action |
| F Physiological Consult | Hand-computed Bayes and E4 browser case |
| G Urgent | Explicit sourced red-flag input, E5 and causal daily follow-up test; no invented population incidence |
| H Failed retry | Full next-day shared-session retry and one-retry accounting test |
| I Adaptive different day | Actual paired fixed/replacement day sets and observable-trigger/deferral precedence tests |
| J Reproducible metrics | Duplicate seeded studies and full 90-row engineering run |
| K Consultation | Ten-state unit test and desktop/mobile delayed request/review/return/acknowledgment |
| L Timeline/Records | Shared measurement transform, selected-page tests and real browser value checks |
| M No hidden/future decisions | Narrow scheduler input, future-input rejection, prior-session bounds, policy visibility masking and chronological scoring |
| N Public safety | Recursive public data checks; production publisher rejects engineering fixture before changing destination |

These establish engineering behavior. Cases B/C/F/J with the new scientific
models remain labeled fixtures until independent written confirmation. No test
result substitutes for research authorization or validates clinical prediction.

## Reproduction

From `backend`:

```powershell
python prepare_public_run.py --output-dir outputs/recovery_public
python evaluate_policies.py --observations outputs/recovery_public/candidates/crew_observations.jsonl --ground-truth outputs/recovery_public/candidates/ground_truth.jsonl --output-dir outputs/recovery_public --use-adaptive-replacement
python publish_frontend_demo_data.py --run-dir outputs/recovery_public --public-dir ../frontend/public/data/pipeline
python -m research_v1.run --engineering-fixture --crew-size 60 --output-dir outputs/recovery_fixture
python -m research_v1.export_fixture --public-dir ../frontend/public/data/fixtures/recovery
python -m pytest -q
```

From `frontend`, run the npm commands above. Install Playwright Chromium with
`npx playwright install chromium` if the test browser is not installed. The
engineering acceptance UI is `/#engineering-dashboard`; the normal demo is
`/#dashboard`. No default research command activates the user-relayed model.
