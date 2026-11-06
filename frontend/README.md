# AstroSentinel — Director's Cut React/Vite frontend

This is an **integration-ready frontend code package**, built on the user's existing React 19 + Vite 8 + Recharts 3 frontend codebase, not a backend fork. No Python backend, registries, Git history or scientific model source is included or modified.

## Run on Windows

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173/`. Use `npm run build` and `npm run lint` to validate.

## Routes (static-host-friendly hash router)

- `/#home` or `/` — cinematic AstroSentinel landing page
- `/#signin` — visual sign-in concept (**no actual authentication**)
- `/#signup` — visual sign-up concept (**no actual authentication**)
- `/#mission` — mission entry gateway
- `/#dashboard` — existing functional presentation dashboard with premium styles
- `/#debug` — original functional debug dashboard, preserved

All buttons are wired to navigation or explicit form feedback. No fake users, authorization, medical results, diagnoses or backend APIs are invented.

## Data contract and safety

`/src/presentation/useMissionData.js` and its original live-use components are preserved. The package ships a **sanitized static v0.6 demo dataset** to render while backend integration proceeds, explicitly not the final scientific experiment. The source loader expects:

- `public/data/pipeline/crew_observations.jsonl`
- `public/data/pipeline/crew_scored.jsonl`
- `public/data/pipeline/simulation_manifest.json`
- `public/data/pipeline/evaluation_blockers.json`

Do **not** publish `ground_truth.jsonl`, hidden event-onset records, or unsanitized aggregate scenario labels. In current backend PR, prefer `backend/publish_frontend_demo_data.py` to generate public files. Schema versions may change once Rahat's updated simulation is implemented—Claude must adapt the frontend against actual model exports, never silently hardcode tiers or risk probabilities.

## Figma

[Landing](https://www.figma.com/design/KfY6biSE6aJEskpP8vfukI?node-id=25-28) | [Canonical older premium dashboard](https://www.figma.com/design/KfY6biSE6aJEskpP8vfukI?node-id=16-4) | [Mission gateway](https://www.figma.com/design/KfY6biSE6aJEskpP8vfukI?node-id=31-28)

The earlier premium dashboard is the design target. Decorative orbit-line diagrams have been replaced with concrete mission-status and link-delay displays in the Figma concepts. The other mission observatory remains only an alternate exploration.

## Git integration

- **Do not overwrite** `main`, `Frontend`, `presentation` or existing integration PRs.
- Start from current approved `origin/main` and inspect changes first.
- Copy/merge only the frontend changes after comparison with current frontend; do not replace newer backend Python files.
- Preserve the existing frontend `PresentationView` playback/ground-comm logic and `App.jsx` debug view.
- Stage and test integration on a new branch, then submit a PR for review.

## Attribution

Hero art is AI-generated for the AstroSentinel project. This is an interface for a synthetic-only NASA Space Apps research prototype, not a medical/clinical software product.
