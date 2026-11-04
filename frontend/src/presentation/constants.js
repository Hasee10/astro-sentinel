// Fixed settings and wording for the presentation view.
// Everything here only describes what the backend sends. Nothing decides risk.

// The presentation view only ever shows the pipeline run. The engineering
// fixtures stay in the debug view, and ground_truth.jsonl is never loaded.
export const DATA = {
  scored: '/data/crew_scored.jsonl',
  observations: '/data/crew_observations.jsonl',
  manifest: '/data/simulation_manifest.json',
  evaluation: '/data/evaluation_blockers.json',
}

export const FALLBACK_SYNTHETIC_LABEL = 'SYNTHETIC – NOT REAL ASTRONAUT DATA'
export const FALLBACK_MISSION_LENGTH = 30

// Playback: 2 seconds per mission day at 1x, so 30 days take about a minute.
export const MS_PER_DAY = 2000
export const SPEEDS = [1, 2, 4]

// The simulated Earth–Mars delay. 1 real second stands for 1 mission minute.
export const DEFAULT_DELAY_MINUTES = 12
export const MAX_DELAY_MINUTES = 20
export const MS_PER_MISSION_MINUTE = 1000

// The two outcomes, always shown separately.
export const OUTCOMES = [
  { key: 'sans', name: 'SANS', body: 'Eye and optic nerve' },
  { key: 'venous', name: 'Venous', body: 'Neck veins' },
]

// Tier order for the legend.
export const TIERS = ['unresolved', 'monitor', 'repeat', 'consult', 'urgent']

// Short label for each tier, plus the action word for word from the brief's
// tier table. "unresolved" has no row in the brief, so it is marked pending.
export const TIER_TEXT = {
  unresolved: { label: 'Unresolved', short: 'Not enough evidence yet', action: 'No action determined – insufficient evidence', pending: true },
  monitor: { label: 'Monitor', short: 'Within personal baseline', action: 'Continue schedule' },
  repeat: { label: 'Repeat', short: 'Retake the measurement', action: 'Repeat or add a measurement' },
  consult: { label: 'Consult', short: 'Earth review needed', action: 'Flag for Earth review, queued for send' },
  urgent: { label: 'Urgent', short: 'Immediate flag', action: 'Immediate flag to the crew medical officer and ground' },
}

// A change to one of these tiers stops playback, in this order for the banner's
// colour when two outcomes change on the same day. Only the backend's tier value
// is compared; this decides nothing about risk.
export const ACTION_TIERS = ['repeat', 'consult', 'urgent']

// Plain words for the backend's tier_reason.
export const REASON_TEXT = {
  red_flag_symptom: 'A red-flag symptom was recorded.',
  measurement_quality: 'Scan quality issue – not a sign of a detected problem.',
  insufficient_evidence_for_probability: 'Not enough evidence to estimate a probability. This does not mean low risk.',
  probability_threshold: 'Set by comparing a simulated probability with the decision thresholds.',
}

export const QUALITY_TEXT = {
  ok: 'Good quality',
  degraded: 'Degraded quality',
  failed: 'Failed quality check',
  unknown: 'Quality unknown',
  not_taken: 'Not taken',
}
