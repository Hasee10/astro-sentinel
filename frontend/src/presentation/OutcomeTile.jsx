import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { QUALITY_TEXT, REASON_TEXT, TIER_TEXT } from "./constants.js";
import { DetailDialog } from "./WorkspaceUI.jsx";

export function OutcomeTile({ meta, outcome }) {
  const [open, setOpen] = useState(false);
  if (!outcome)
    return (
      <article className="pv-tile">
        <h3>{meta.name}</h3>
        <p>No assessment for this day.</p>
      </article>
    );
  const tier = TIER_TEXT[outcome.tier] ? outcome.tier : "unresolved";
  const text = TIER_TEXT[tier];
  const hasEstimate =
    outcome.probability !== null && outcome.probability !== undefined;
  const entries = [
    { label: "Recorded explanation", text: outcome.explanation },
    {
      label: "Action",
      text: `${text.action}${text.pending ? " (wording pending clinical lead)" : ""}`,
    },
    {
      label: "Measurement quality",
      text: QUALITY_TEXT[outcome.measurement_quality] ?? "Unavailable",
    },
    ...(!hasEstimate
      ? [
          {
            label: "Probability",
            text: "No estimate is available. This does not mean zero risk.",
          },
        ]
      : [
          {
            label: "Probability",
            text:
              outcome.probability_label ?? "Unvalidated simulation estimate",
          },
        ]),
    ...(outcome.limitations ?? []).map((limit) => ({
      label: "Limitation",
      text: limit,
    })),
    {
      label: "Evidence references",
      text:
        outcome.evidence_references
          ?.map((id) => id.replaceAll("_", " "))
          .join(" · ") || "None recorded",
    },
  ];
  return (
    <article className={`pv-tile pv-tier-${tier}`}>
      <header className="pv-tile-head">
        <span className={`pv-outcome-icon pv-outcome-${meta.key}`}>
          <Icon name={meta.key === "sans" ? "eye" : "pulse"} size={22} />
        </span>
        <div>
          <h3>{meta.name}</h3>
          <span>{meta.body}</span>
        </div>
        <span className="pv-status-dot" />
      </header>
      <div className="pv-tile-tier">{text.label}</div>
      <p className="pv-tile-short">
        {outcome.tier_reason === "measurement_quality"
          ? "Measurement needs repeating"
          : text.short}
      </p>
      <p className="pv-tile-reason">
        {REASON_TEXT[outcome.tier_reason] ??
          "See the recorded evidence for this assessment."}
      </p>
      <div className="pv-prob">
        {hasEstimate ? (
          <>
            <strong>{Math.round(outcome.probability * 100)}%</strong>
            <span>
              {outcome.probability_label || "Unvalidated simulation estimate"}
            </span>
          </>
        ) : (
          <>
            <strong>—</strong>
            <span>Probability unavailable</span>
          </>
        )}
      </div>
      <button
        type="button"
        className="pv-evidence-button"
        onClick={() => setOpen(true)}
      >
        View evidence
        <Icon name="external" size={16} />
      </button>
      {open && (
        <DetailDialog
          title={`${meta.name} · recorded evidence`}
          entries={entries}
          onClose={() => setOpen(false)}
        />
      )}
    </article>
  );
}
