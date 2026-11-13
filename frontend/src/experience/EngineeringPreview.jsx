import { useMissionData } from "../presentation/useMissionData.js";
import { evidenceFor, indexMission, observationRows } from "../presentation/missionModel.js";
import { QUALITY_TEXT, TIER_TEXT } from "../presentation/constants.js";

export default function EngineeringPreview({ navigate, researchCohortSize }) {
  const data = useMissionData(true);
  if (data.status !== "ready") return <div className="as-live-preview" role="status">
    <h3>Engineering preview</h3><p>{data.status === "error" ? "Current demonstration data could not be loaded. No example values are substituted." : "Loading the current recorded engineering example…"}</p>
  </div>;
  const id = "E4", day = 14;
  const indexed = indexMission(data.scored, data.observations ?? []);
  const assessment = indexed.crew.get(id)?.find(record => record.as_of_day === day);
  const observation = indexed.scans.get(`${id}:${day}`);
  if (!assessment || !observation || observation.metadata.run_id !== assessment.run_id) return <div className="as-live-preview"><h3>Engineering example unavailable</h3><p>No coherent same-run observation and assessment are available for this preview.</p></div>;
  const rows = observationRows(indexed.scans, id, 30);
  return <div className="as-live-preview" aria-label="Current engineering data preview" data-profile={id} data-day={day} data-run={assessment.run_id}>
    <div className="as-live-preview-heading"><div><span className="as-preview-tag">Illustrative engineering simulation — not clinically validated.</span><h3>Profile {id} · Mission day {day}</h3></div>
      <span>{indexed.ids.length} acceptance profiles<br />Separate from {researchCohortSize ? `the ${researchCohortSize}-profile research cohort` : "the research cohort"}</span></div>
    <div className="as-preview-outcomes">{["sans", "venous"].map(outcome => {
      const evidence = evidenceFor(rows, day, outcome).latestUsable;
      const result = assessment[outcome];
      return <article key={outcome} className={`as-preview-outcome pv-tier-${result.tier}`}>
        <header><h4>{outcome === "sans" ? "SANS" : "Venous"}</h4><strong>{TIER_TEXT[result.tier]?.label ?? "Unresolved"}</strong></header>
        <div className="as-preview-probability">{Number.isFinite(result.probability) ? `${(result.probability * 100).toFixed(1)}%` : "Unavailable"}<span>Hypothetical monitoring estimate</span></div>
        <dl><div><dt>{outcome === "sans" ? "ONSD" : "Jugular area"}</dt><dd>{evidence ? `${evidence.value.toFixed(outcome === "sans" ? 2 : 1)} ${outcome === "sans" ? "mm" : "mm²"}` : "Unavailable"}</dd></div>
          <div><dt>Quality / scan day</dt><dd>{QUALITY_TEXT[evidence?.quality] ?? "Unavailable"} · {evidence?.day ?? "—"}</dd></div>
          {outcome === "venous" && <div><dt>Flow class</dt><dd>{evidence?.flow ?? "Unavailable"}</dd></div>}</dl>
        <p>{result.recommended_action?.text ?? "Review the recorded assessment."}</p>
      </article>;
    })}</div>
    <p className="as-preview-run">Run {assessment.run_id} · Adaptive replacement · Same profile, run and mission day. User-relayed model pending independent written confirmation.</p>
    <button type="button" className="as-primary" onClick={() => navigate(`engineering-dashboard?profile=${id}&day=${day}`)}>Explore this exact example</button>
  </div>;
}
