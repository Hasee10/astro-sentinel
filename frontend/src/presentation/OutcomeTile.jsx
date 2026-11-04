import { useId } from 'react'
import { REASON_TEXT, TIER_TEXT } from './constants.js'

// "onsd_measurement_protocol" -> "ONSD measurement protocol"
function readable(id) {
  return id
    .split('_')
    .map((word) => (['onsd', 'hrv', 'ptt', 'sans', 'oct'].includes(word) ? word.toUpperCase() : word))
    .join(' ')
}

// The probability, only as the backend sent it. Null is "no estimate", never 0.
function Probability({ outcome }) {
  if (outcome.probability === null || outcome.probability === undefined) {
    return <span className="pv-prob pv-prob--none">No estimate</span>
  }
  return (
    <span className="pv-prob">
      <strong>{Math.round(outcome.probability * 100)}%</strong>
      <span className="pv-prob-label">{outcome.probability_label || 'Unvalidated simulation estimate'}</span>
    </span>
  )
}

// One outcome (SANS or Venous) for one day. The short status is always visible.
// The full reasoning appears in a popover on hover, keyboard focus, or tap.
//   compact = the smaller version used in the ground panel
export function OutcomeTile({ meta, outcome, compact = false }) {
  const popoverId = useId()
  if (!outcome) return null
  const tier = TIER_TEXT[outcome.tier] ? outcome.tier : 'unresolved'
  const text = TIER_TEXT[tier]

  return (
    <div
      className={`pv-tile pv-tier-${tier}${compact ? ' pv-tile--compact' : ''}`}
      tabIndex={0}
      aria-describedby={popoverId}
    >
      <div className="pv-tile-head">
        <span className="pv-tile-name">{meta.name}</span>
        <span className="pv-tile-body">{meta.body}</span>
      </div>
      <div className="pv-tile-tier">{text.label}</div>
      <div className="pv-tile-short">{text.short}</div>
      {!compact && <Probability outcome={outcome} />}
      <span className="pv-tile-hint" aria-hidden="true">i</span>

      <div className="pv-pop" role="tooltip" id={popoverId}>
        <p className="pv-pop-action">
          <span>Action</span>
          {text.action}
          {text.pending && <em> (wording pending clinical lead)</em>}
        </p>
        {outcome.tier_reason && <p><span>Why</span>{REASON_TEXT[outcome.tier_reason] ?? outcome.tier_reason}</p>}
        {outcome.measurement_quality && <p><span>Scan quality</span>{outcome.measurement_quality}</p>}
        {outcome.limitations?.length > 0 && (
          <p><span>Limits</span>{outcome.limitations[0]}</p>
        )}
        {outcome.evidence_references?.length > 0 && (
          <p><span>Based on</span>{outcome.evidence_references.map(readable).join(', ')}</p>
        )}
      </div>
    </div>
  )
}
