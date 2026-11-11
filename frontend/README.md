# AstroSentinel frontend

A React 19 / Vite 8 research demonstration for NASA Space Apps 2026. The public site introduces the mission; the operational workspace renders the backend's independent SANS and venous assessments across a synthetic cohort. It does not calculate clinical probabilities or generate medical observations.

## Run and verify

```powershell
cd frontend
npm ci
npm run dev
```

Use the Local URL printed by Vite. Verification commands:

```powershell
npm run check:data
npm test
npm run lint
npm run build
```

The production build is `dist/`, deployable to a static host. Hash routing requires no server-side rewrites. The operational workspace and diagnostics load lazily so the landing page does not download the chart runtime immediately.

## Views

| Route           | Purpose                                                                        |
| --------------- | ------------------------------------------------------------------------------ |
| `/#home` or `/` | Mission introduction, approach, and data-derived preview                       |
| `/#mission`     | Three perspective-specific entry points                                        |
| `/#dashboard`   | Searchable cohort, independent assessments, measurements, charts               |
| `/#ground`      | Delivered Earth snapshots, acknowledgements, transmission history              |
| `/#timeline`    | Causal charts, tier strips, recorded changes, observation table                |
| `/#research`    | Evaluation blockers, generation readiness, run provenance                      |
| `/#debug`       | Integration diagnostics, older examples, engineering fixtures, reveal-all mode |

Profile selection, playback day, and communication state persist between the four operational views. Selecting another astronaut resets that profile's playback and transmissions. Returning to the public site or reloading starts a fresh session. No authentication is enabled; old sign-in/sign-up hashes fall back to home.

The operational views and mission gateway fit the viewport without page scrolling. The cohort, records, messages, and readiness lists are paginated; page size adapts to actual available panel space. Overview separates assessments and measurements. Timeline separates charts, changes, and records, with a second chart toggle for ONSD trace or tier history. Earth link separates the received snapshot, sending controls, and transmission history. Research separates summary, blockers, models, and provenance. On phones, users select SANS or venous to inspect one readable assessment at a time. Evidence opens in keyboard-accessible, paginated dialogs; source text is preserved in full.

The cohort browser has search and separate outcome/status filters. Its status markers use only records through the selected day. Charts, event history, and observation tables hide future records. A playback transition into a backend action tier can pause the mission; manually selecting a day pauses playback. Playback settings include speed and pause-on-action controls. One real second represents one simulated communication minute, independently of playback speed. Skip delay delivers the oldest in-flight message. Earth never reads directly from the current onboard record. The legacy `#debug` route remains a developer integration tool rather than a client navigation destination.

## Data contract

The workspace consumes only the sanitized static files in `public/data/pipeline`:

- `crew_scored.jsonl` (required)
- `crew_observations.jsonl`, `simulation_manifest.json`, `evaluation_blockers.json` (optional, with explicit unavailable states)

The current dataset contains 300 synthetic profiles over 30 days, not a 300-person onboard crew. The landing-page cohort size and mission window come from the manifest. This is an engineering demonstration, not a completed scientific experiment.

Keep SANS and venous independent. Null probability is unavailable, never zero or low risk. A measurement-quality Repeat is not physiological event detection. Every numeric estimate and tier comes from backend output. Never publish `ground_truth.jsonl`, hidden event fields, unsanitized ground-truth status counts, or `scenario_counts`. Prefer `backend/publish_frontend_demo_data.py` for publishing a replacement run. `npm run check:data` validates the public-data boundary.

## Design assets

- `src/components/Icon.jsx`: original SVG interface icons.
- `public/favicon.svg`: AstroSentinel mark.
- `public/images/astrosentinel-mark.svg` / `.png` and `astrosentinel-logo.svg` / `.png`: original orbital-A logo and horizontal wordmark. The mark is used across the site and workspace.
- `public/images/mission-link.svg`: original vector communication illustration.
- `public/images/mission-preview.svg` and `.png`: fixed day-10 visualization generated from the first profile's actual public observations and assessments. The SVG is used on the landing page; the PNG is a shareable raster export. Neither is live telemetry or a screenshot of the whole workspace.

Run `npm run assets` after changing the public demo dataset. The preview generator refuses incomplete day-10 input and excludes failed ONSD values. It does not invent measurements, personal baselines, clinical thresholds, or results. Hero art is the project's existing AI-generated illustration. Manrope is bundled locally via Fontsource.

The earlier [Figma landing](https://www.figma.com/design/KfY6biSE6aJEskpP8vfukI?node-id=25-28), [dashboard](https://www.figma.com/design/KfY6biSE6aJEskpP8vfukI?node-id=16-4), and [gateway](https://www.figma.com/design/KfY6biSE6aJEskpP8vfukI?node-id=31-28) remain historical references; this redesign is implemented in the repository, not synchronized back to Figma.
