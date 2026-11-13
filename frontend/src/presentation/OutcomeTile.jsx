import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { QUALITY_TEXT, REASON_TEXT, TIER_TEXT } from "./constants.js";
import { DetailDialog } from "./WorkspaceUI.jsx";
import { evidenceFor, nextEvidenceAction } from "./missionModel.js";

export function OutcomeTile({ meta, outcome, rows = [], day, missionLength = 30, consultation, onTimeline, onSchedule, onConsultation }) {
  const [open, setOpen] = useState(false);
  if (!outcome) return <article className="pv-tile"><h3>{meta.name}</h3><p>No assessment for this day.</p></article>;
  const tier = TIER_TEXT[outcome.tier] ? outcome.tier : "unresolved";
  const hasEstimate = Number.isFinite(outcome.probability);
  const evidence = evidenceFor(rows, day ?? 0, meta.key);
  const reading = evidence.latestUsable;
  const latest = evidence.latest;
  const jugular = meta.key === "venous";
  const unit = jugular ? "mm²" : "mm";
  const digits = jugular ? 1 : 2;
  const delta = reading && Number.isFinite(reading.baseline) ? reading.value - reading.baseline : null;
  const action = outcome.recommended_action;
  const fullReason = outcome.explanation ?? "No explanation was recorded.";
  const shortReason = fullReason.length > 280 ? `${fullReason.slice(0, 277)}…` : fullReason;
  const entries = [
    { label: "Recorded explanation", text: fullReason },
    { label: "Recommended action", text: action?.text ?? TIER_TEXT[tier].action },
    { label: "Follow-up rule", text: action?.follow_up_rule ?? "Timing unavailable" },
    { label: "Model label", text: outcome.probability_label ?? "No monitoring estimate available" },
    ...(outcome.limitations ?? []).map(text => ({ label: "Limitation", text })),
    { label: "Sources", text: outcome.evidence_references?.join(" · ") || "No reference recorded" },
  ];
  return <article className={`pv-tile pv-tier-${tier}`} aria-label={`${meta.name} assessment`}>
    <header className="pv-tile-head"><span className={`pv-outcome-icon pv-outcome-${meta.key}`}><Icon name={jugular ? "pulse" : "eye"} size={22} /></span>
      <div><h3>{meta.name}</h3><span>{meta.body}</span></div><span className="pv-status-dot" /></header>
    <div className="pv-assessment-heading"><strong className="pv-tile-tier">{TIER_TEXT[tier].label}</strong>
      <div className="pv-estimate"><strong>{hasEstimate ? `${(outcome.probability * 100).toFixed(1)}%` : "Unavailable"}</strong><span>Hypothetical estimate</span></div></div>
    <p className="pv-model-label" title={outcome.probability_label ?? undefined}>{outcome.probability_label?.includes("ENGINEERING FIXTURE") ? "Engineering fixture · user-relayed model · unvalidated" : outcome.probability_label ?? "No authorized estimate available. Missing evidence is not zero risk."}</p>
    <section className="pv-card-section"><h4>Recorded evidence</h4>
      <dl className="pv-evidence-grid">
        <div><dt>Latest readable {jugular ? "area" : "ONSD"}</dt><dd>{reading ? `${reading.value.toFixed(digits)} ${unit}` : "Unavailable"}</dd></div>
        <div><dt>Personal baseline</dt><dd>{reading?.baseline != null ? `${reading.baseline.toFixed(digits)} ${unit}` : "Unavailable"}</dd></div>
        <div><dt>Change from baseline</dt><dd>{delta == null ? "Unavailable" : `${delta >= 0 ? "+" : ""}${delta.toFixed(digits)} ${unit}${jugular && reading.baseline > 0 ? ` (${(delta / reading.baseline * 100).toFixed(1)}%)` : ""}`}</dd></div>
        <div><dt>Reading day</dt><dd>{reading ? `Day ${reading.day}` : "None available"}</dd></div>
        <div><dt>Latest acquisition quality</dt><dd>{QUALITY_TEXT[latest?.quality ?? outcome.measurement_quality] ?? "Unavailable"}{latest ? ` · day ${latest.day}` : ""}</dd></div>
        {jugular && <div><dt>Flow class</dt><dd>{reading?.flow ?? "Unavailable"}</dd></div>}
      </dl>
      {!reading && <p>No usable {jugular ? "jugular" : "ONSD"} observation is available in this visible history. Inspect the missing input before interpreting risk.</p>}
      {reading?.quality === "degraded" && <p className="pv-warning-text">This readable observation is degraded; its model evidence weight is limited.</p>}
    </section>
    <section className="pv-card-section"><h4>Why this tier?</h4><p className="pv-reason-label">{REASON_TEXT[outcome.tier_reason] ?? "Review the recorded assessment reason."}</p><p className="pv-recorded-reason">{shortReason}</p></section>
    <section className="pv-card-section"><h4>What happens next?</h4><p>{action?.text ?? TIER_TEXT[tier].action}</p>
      <p className="pv-follow-up">{nextEvidenceAction(outcome, day ?? 0, evidence.summary.policy, missionLength)}</p>
      <dl className="pv-evidence-grid"><div><dt>Acquisition retry</dt><dd>{action?.quality_repeat_required ? "Required" : "Not currently requested"}</dd></div>
        <div><dt>Action status</dt><dd>{action?.status ?? "Not recorded"}</dd></div>
        <div><dt>Consultation</dt><dd>{consultation ? consultation.state.replaceAll("_", " ") : action?.ground_review_required ? "Review suggested · not yet requested" : "No request pending"}</dd></div></dl>
    </section>
    <div className="pv-card-actions"><button type="button" className="pv-btn" onClick={() => setOpen(true)}>View evidence</button>
      {onTimeline && <button type="button" className="pv-text-button" onClick={() => onTimeline(reading?.day ?? day)}>Open timeline evidence</button>}
      {onSchedule && <button type="button" className="pv-text-button" onClick={onSchedule}>View scan schedule</button>}
      {onConsultation && <button type="button" className="pv-text-button" onClick={onConsultation}>{consultation ? "Open consultation details" : "Consultation workspace"}</button>}</div>
    {open && <DetailDialog title={`${meta.name} · recorded evidence`} entries={entries} onClose={() => setOpen(false)} />}
  </article>;
}
