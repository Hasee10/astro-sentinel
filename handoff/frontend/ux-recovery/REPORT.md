# Frontend visualization and responsive UX recovery

Implemented locally from checkpoint `cd786d0` on `main`. The scientific engine,
approval gates, 300-profile research dataset and E1–E5 acceptance observations
are unchanged. A recoverable pre-change bundle is at
`D:/astro-sentinel-before-frontend-ux.bundle`. No push or deployment was performed.
The final remote check found the local scientific checkpoint one commit ahead of
remote main, with no incoming commits to overwrite.

## Why the chart line disappeared

The previous `TrendsPanel` supplied Recharts with one row for every mission day.
After acquisition became policy-scheduled, unscanned days correctly had null
measurement values. The line explicitly used `connectNulls={false}`. Every null
day therefore broke the line; isolated scan days appeared only as points. This
was a data-series/rendering issue, not a missing CSS stroke or a need for daily
scan generation. Failed-only histories also lost the entire chart because the
old Y-range depended on finding a measured value first.

## Sparse observations

`sparseObservations()` filters to the visible mission day, preserves actual scan
days and keeps measurement data separate from connector geometry. It never
creates daily or interpolated samples. Failed values remain null even if an
inconsistent input contains a number.

The default Connected trend draws 2.3 px guide segments between consecutive
readable good/degraded acquisitions. Segments crossing missing days are dashed;
the legend explicitly says they are visual guides, not measured or interpolated
physiology. Observed points removes all guide segments. Good points are filled;
degraded or unknown-quality readings use hollow amber markers. Unknown-quality
readings are displayed but not used to construct usable-evidence connectors.

Failures appear on a separate acquisition rail at their actual day, with no
invented Y-value. Each failure links to its matching record. One reading remains
a point; no readings or failed-only histories have truthful empty states and
retain failure information. The horizontal range ends at the selected mission
day; future values and future baseline observations cannot change it or its
Y-domain. Baseline reference lines are personal measurements, not clinical
cutoffs.

Both ONSD and jugular charts use the same transformation. Tooltips and accessible
measurement tables show the same rounded values as Records: ONSD in mm, jugular
area in mm², baseline, change and flow. Tooltips use high-contrast backgrounds.
The accessible table provides keyboard-operable links to actual records.
Summaries derive actual shared-session count, usable readings, degraded/failed
acquisitions, last scan day and active policy from the loaded observations.

## Evidence cards and navigation

Each outcome now has compact sections for tier/probability/model label, recorded
evidence, why the tier was assigned, and next action. SANS shows latest readable
ONSD, personal baseline, change, reading day and latest acquisition quality.
Venous independently shows area, baseline/percentage change, flow and quality.
The newest acquisition and latest readable evidence are distinguished when a
scan fails. Degraded evidence is labeled as limited-weight evidence.

Reason text comes from the backend assessment, including quality Repeat,
physiological threshold crossing, insufficient evidence, retained serious
evidence and red flags. Full source explanation and limitations remain available
in the evidence dialog. The visible engineering label uses sentence case; its
full original model label remains in the dialog and title text.

Actions expose retry requirement, action status and current consultation state.
Fixed routine targets are calculated from the declared Day 1 seven-day anchor.
Adaptive follow-up targets use the supplied backend target and explicitly state
that this is not a confirmed future acquisition. The frontend never inspects
future observations to predict the next scan day.

View evidence, Open timeline evidence, View scan schedule and Consultation
workspace are working controls. Card evidence opens the corresponding Records
page; schedule decisions show only days already reached; consultation state is
the actual local session state. Records show separate jugular quality and flow.
Collections use stable page sizes in the content-driven layout rather than
feeding their own natural height back into the old fixed-screen pager.

## Landing preview and data contexts

The old preview was a generated SVG image from a prior A1 research run. It is no
longer used by the landing page. The replacement loads actual acceptance
observations and assessments at runtime and checks same-run coherence.

The selected example is **E4, day 14, run engineering-42**:

| Field | Actual displayed value |
|---|---|
| ONSD | 6.12 mm, good quality |
| SANS | Consult, hypothetical 47.8% |
| Jugular area | 58.7 mm², good quality |
| Flow | Retrograde |
| Venous | Repeat, hypothetical 34.5% |

The preview states “Illustrative engineering simulation — not clinically
validated.” Its action opens that same profile and day. The acceptance-profile
count comes from the loaded fixture; the separate research-cohort count comes
from its manifest. No E-profile is renamed A1, and missing preview data receive
an unavailable state rather than substituted numbers. The static old preview
assets remain historical unused files; no unrelated brand assets were replaced.

## Engineering Comparison

Added a dedicated Engineering Comparison tab, separate from Results and the
scientific approval/readiness views. Its new public artifact contains only an
allowlisted projection of the existing 90 aggregate result rows from
`handoff/research_lead/RECOVERY_ENGINEERING_RESULTS.json`. It includes source and
specification fingerprints, seeds, configuration, metrics and limitations.
No per-profile truth, condition identity, susceptibility or onset is published.

The UI filters trigger-window usefulness and evidence half-life, pairs all three
seeds, and weights mean delay by detected-event count. At 0.7 and seven days it
shows 1,068 fixed versus 1,579 adaptive sessions, and 2 versus 9 missed SANS
events. It states adaptive used 511 more sessions and does not claim superiority.
Means conditional on detection and false-escalation assessment-day counting are
explained. All outputs retain `validated_for_experiment=false`.

Reproduce the safe aggregate projection with `npm run publish:engineering`.
No simulation, cohort, probability, scientific formula or tier distribution was
regenerated or altered for this task. Existing pipeline and fixture JSONL files
are byte-for-byte unchanged from the scientific checkpoint.

## Typography, layout and accessibility

- Workspace headings use 26–32 px; gateway headings 30–34 px; section/card
  headings approximately 19–24 px; body 15–16 px; secondary labels 13–15 px.
  Meaningful chart ticks and constrained helpers are at least 12–13 px. The
  landing hero retains its approved larger display typography.
- Removed all sub-12 px font declarations in the presentation and experience
  styles. Updated spacing and content layout with the larger type.
- Replaced rigid viewport-height constraints with natural page scrolling and
  content-sized cards. This also fixes gateway actions overflowing their cards
  after text enlargement, while preserving the one-left/two-right desktop layout.
- Both assessment cards stack at mobile widths. A visual review caught the old
  mobile `display:flex` rule overriding grid templates; the fix explicitly restores
  grid display, and a geometry assertion now checks that cards actually stack.
- Desktop profile navigation is 210 px wide. Tablet/mobile use an accessible
  collapsible profile browser. The selection is revealed on initial deep links,
  labels distinguish Engineering cases from Research cohort, and the bounded
  list shows multiple profiles instead of self-collapsing to one row.
- Mobile workspace navigation has a labeled menu button with expanded state.
  Tabs wrap, dialogs scroll within the viewport, and interactive controls have
  comfortable 44 px targets. Focus indicators and keyboard tab navigation remain
  available. Charts and legends reflow without page-wide horizontal overflow.

## Verification and screenshots

| Check | Result |
|---|---|
| Frontend unit tests | 14 passed |
| Browser acceptance | 17 passed: desktop/mobile operational cases, five-width visual matrix, coherent preview/results, tooltip/record agreement, empty/error, profile switch/day rewind and navigation |
| Full backend suite | 316 passed; backend implementation unchanged |
| Public-data checks | Passed; 9,000 research observations/assessments, every fixture/manifest, and 90 aggregate engineering rows |
| Frontend lint / production build | Passed |
| Responsive widths | 375, 390, 768, 1280 and 1440 px |
| 200% reflow equivalent | Passed at 720×500 CSS pixels with DPR 2 for a 1440×1000 physical viewport; dialog keyboard dismissal checked |
| Actual native Chrome 200% zoom | **Unverified:** Computer Use stopped because it could not determine the current Chrome URL confidently enough to enforce its policy. Native browser interaction was stopped; no barrier was bypassed |

Screenshots were captured and visually reviewed; this found and corrected actual
mobile stacking, sidebar pagination, chart unit-label overlap and gateway action
overflow defects beyond the original checks. The attachment supplied the task
text, not separate screenshot files; the existing local UI was inspected directly.

See [SCREENSHOTS.md](SCREENSHOTS.md) for the screenshot index and
[CHANGED_FILES.json](CHANGED_FILES.json) for exact changed files.

## Remaining restrictions

Scientific authorization blockers from the prior recovery remain unchanged.
The engineering comparison is not approved science, and fixture probabilities
remain unvalidated. Real native browser 200% zoom needs a manual check because
the native verification tool stopped; automated equivalent reflow coverage is
complete. Native iOS Safari was not tested. Existing deployment was preserved.
