# Recovery specification confirmation

Status: **pending independent written confirmation**. The user relayed these
research-lead specifications in the Codex chat on 2026-11-13. This is evidence of
the user's instructions and the model's provenance; it is not an independently
verified signed Rahat approval. No registry approvals have been invented.

The complete versioned parameter set and all pending interpretations are in
[`backend/research_v1/spec.json`](../../backend/research_v1/spec.json), version
`user-relayed-2026-11-13-v1`, canonical JSON SHA256 (UTF-8, sorted keys, compact separators)
`dd3f16e5cd13d2f7f156a1fcf5b98ca2678225160719661d6187fe1de625374c`.

## Confirmation requested from Rahat

Please confirm this exact version and hash for **hypothetical synthetic research
only**, and answer the following interpretation questions. An amendment requires
a new version and hash rather than an informal boolean change.

1. Does the 0.1 percentage-point/day SANS monitoring prior supersede the historical
   0.5 percentage-point/day *generation-only* prior? Baseline 5.35 mm, SD 0.25 mm,
   clipping 4.8–5.9 mm and within-person SD 0.2 mm already match the active approval.
   Confirm the additional observer noise 0.1 mm, amplitudes 0.3–1.0 mm and
   6–10 day capped ramps. The historical
   +0.04 mm/day external-CSV candidate is excluded.
2. Confirm that LR+ 7.2 and LR− 0.07 are hypothetical model inputs, **not** reuse
   of a validated ONSD-to-SANS diagnostic LR or OCT classifier performance.
   Should evidence use only the latest readable observation with decayed log LR,
   or some specified longitudinal aggregation? Engineering currently uses only
   the latest observation and never multiplies correlated daily LRs.
3. Confirm 0.2 log-LR weight for degraded readable scans, versus the historical
   exclusion of degraded evidence. For the 10% acquisition problems, confirm
   whether the historical 50/50 degraded/failed split and ONSD +0.4 mm off-axis
   bias remain valid. What is the intended jugular degradation model?
4. Confirm independent 30% venous occurrence, integer onset 3–15, baseline
   34 mm² with 20% SD, 10% measurement noise, 7-day ramp toward 1.5–3× baseline,
   and the **synthetic** 108 mm² latent cap. Are positive-truncated Gaussian
   baselines and Gaussian proportional measurement errors acceptable? Confirm
   healthy 8% stagnant and 2% retrograde readings are mutually exclusive and
   apply before onset in future event cases too. Is the latent cap allowed to be
   exceeded by noisy measurements? Engineering currently allows that.
5. Retain the historical 5% venous monitoring prior separately from 30% event
   prevalence? Confirm latest-flow LR decay and that area >1.2× baseline sets a
   minimum Repeat tier only, with no disease probability inferred from area.
6. Confirm a full shared-session next-day retry when either measurement is
   inadequate. Does the one-retry limit forbid retry chains? Engineering says
   yes; subsequent tier-driven follow-up remains a separate reason for scanning.
   Are fixed-policy Consult/Urgent follow-ups required in addition to anchors and
   retries? Engineering fixed currently performs anchors plus retries only.
7. Confirm adaptive precedence: initial scan → one next-day acquisition retry →
   Urgent follow-up → Repeat/Consult follow-up → 14-day backstop → trigger scan →
   routine/deferral. Trigger minimum interval is 2 days; urgent/retry exceptions
   can scan next day. Follow-up due dates are measured from the latest session,
   not reset daily by repeated assessments.
8. What exactly are the trigger's "required evidence conditions"? Engineering
   requires an observed trigger for either outcome, no fully good shared session
   within the three-day window, and a two-day interval. Three-day lookback means
   current day and the preceding two days. Confirm whether "usable recent scan"
   instead includes readable degraded measurements or only one outcome.
9. Is routine deferral permitted only when both outcomes are Monitor, the last
   session is usable and no recent trigger exists? Engineering says yes. Confirm
   the ordinary seven-day interval is measured from the most recent session.
10. Confirm persistence: Urgent never clears automatically; a failed scan cannot
    clear Consult. Can a newer usable observation lower Consult? What explicit
    resolution rule should eventually clear Urgent? Closing a communication case
    currently never clears a monitoring alert.
11. What observable preflight information assigns 5% versus 10% SANS priors?
    Engineering supplies a clearly synthetic preflight prior, generated alongside
    susceptibility; the monitor never receives the susceptibility/event labels.
12. Confirm communication delay as an operator-selected demonstration setting,
    rather than a sampled or scientifically approved Mars-delay distribution.
    Consultation responses concern evidence review and follow-up only, without
    treatment instructions or claims that a real doctor is connected.

## Existing approvals preserved

The eight Rahat-attributed assumptions already recorded in the repository remain
active as documented. The seven-day Day 1 anchor, 15/40/80% synthetic thresholds,
historical venous prior-odds × latest-flow LR, SANS susceptibility/event rates and
the windowed trigger mechanism are implemented without relabeling their scope.
The newer conflicting parameters remain outside these active assumptions.

The original Lee et al. 2020 paper establishes **103 mm²** for the supine 1g
reference, not 108. Both source DOCX files contain 108 and have been preserved.
The registry now records 103 and the correction provenance. This literature
correction does not authorize any venous disease threshold or the synthetic cap.
Source: [Lee et al., Results](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2020.00863/full).

## Execution boundary

`python -m research_v1.run` refuses research execution by default. The explicit
`--engineering-fixture` mode runs the new implementation with a conspicuous
label and `validated_for_experiment=false`. It cannot set approvals or publish
production results. The normal `evaluate_policies.py` readiness gate still blocks
the full experiment. The old adaptive execution flag remains false because its
comment explicitly requires **both approval and integration**, neither of which
the new engineering runner pretends to satisfy.

After written confirmation, reconcile the active registry, complete the specified
interpretations, integrate the approved runner into the production evaluation
entry point, regenerate the study and sanitized data, then repeat the acceptance
and public-data checks before considering deployment.
