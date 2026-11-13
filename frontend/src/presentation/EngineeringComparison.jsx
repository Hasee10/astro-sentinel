import { useEffect, useState } from "react";
import { summarizeComparison } from "./comparisonModel.js";

export default function EngineeringComparison() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [sensitivity, setSensitivity] = useState(0.7);
  const [halfLife, setHalfLife] = useState(7);
  useEffect(() => {
    let cancelled = false;
    fetch("/data/engineering/comparison.json").then(response => {
      if (!response.ok) throw new Error("Comparison unavailable");
      return response.json();
    }).then(report => { if (!cancelled) setData(report); }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, []);
  const comparison = data && summarizeComparison(data, sensitivity, halfLife);
  if (error || (data && !comparison)) return <section className="pv-panel"><h2>Engineering comparison unavailable</h2><p>No coherent labeled comparison could be loaded. No replacement values or scientific conclusions are supplied.</p></section>;
  if (!comparison) return <section className="pv-panel" role="status"><h2>Loading engineering comparison</h2><p>Reading the existing computed aggregate results.</p></section>;
  const fixed = comparison.fixed, adaptive = comparison.adaptive_replacement;
  const difference = adaptive.sessions - fixed.sessions;
  const cells = [
    ["Shared scan sessions", fixed.sessions, adaptive.sessions],
    ["Retry sessions", fixed.repeat_sessions, adaptive.repeat_sessions],
    ["Good measurements", fixed.successful_measurements, adaptive.successful_measurements],
    ["Degraded / failed measurements", `${fixed.degraded_measurements} / ${fixed.failed_measurements}`, `${adaptive.degraded_measurements} / ${adaptive.failed_measurements}`],
  ];
  return <section className="pv-panel pv-comparison">
    <header className="pv-panel-head"><h2>Engineering Comparison</h2><span className="pv-tag">Not validated scientific findings</span></header>
    <p className="pv-notice">{data.label}. These aggregate results test a user-relayed model and pending scheduling interpretations. They do not establish clinical performance or approved research conclusions.</p>
    <p>{data.cohort_size_per_seed} generated profiles per seed · seeds {data.seeds.join(", ")} · {data.rows[0].days}-day missions · {data.rows.length} computed policy rows. Separate from the E1–E5 acceptance examples and the 300-profile research cohort.</p>
    <div className="pv-comparison-controls"><label>Trigger-window usefulness <select value={sensitivity} onChange={event => setSensitivity(Number(event.target.value))}>{[...new Set(data.rows.map(row => row.trigger_sensitivity))].sort().map(value => <option value={value} key={value}>{value.toFixed(1)}</option>)}</select></label>
      <label>Evidence decay half-life <select value={halfLife} onChange={event => setHalfLife(Number(event.target.value))}>{[...new Set(data.rows.map(row => row.half_life_days))].sort((a,b) => a-b).map(value => <option value={value} key={value}>{value} days</option>)}</select></label></div>
    <h3>Scan burden · totals across selected seeds</h3>
    <div className="pv-table-wrap"><table className="pv-data-table"><thead><tr><th>Metric</th><th>Fixed</th><th>Adaptive replacement</th></tr></thead><tbody>{cells.map(([label, a, b]) => <tr key={label}><th scope="row">{label}</th><td>{a.toLocaleString()}</td><td>{b.toLocaleString()}</td></tr>)}</tbody></table></div>
    <p className="pv-comparison-finding">Adaptive used {Math.abs(difference).toLocaleString()} {difference >= 0 ? "more" : "fewer"} sessions at these settings. Scan burden and missed events must be considered alongside delay; a shorter delay among detected cases alone does not establish superiority.</p>
    {["sans", "venous"].map(outcome => <div key={outcome}><h3>{outcome === "sans" ? "SANS" : "Venous"} outcomes</h3><div className="pv-table-wrap"><table className="pv-data-table"><thead><tr><th>Metric</th><th>Fixed</th><th>Adaptive</th></tr></thead><tbody>
      {[["Detected events", "detected"], ["Missed events", "missed"], ["False Consult/Urgent assessment-days", "falseDays"], ["Mean delay among detected cases", "delay"]].map(([label, key]) => <tr key={key}><th scope="row">{label}</th>{[fixed, adaptive].map((policy, i) => <td key={i}>{key === "delay" ? policy[outcome].delay == null ? "Unavailable" : `${policy[outcome].delay.toFixed(2)} days` : policy[outcome][key]}</td>)}</tr>)}
    </tbody></table></div></div>)}
    <p>Technical quality Repeat is excluded from physiological event detection. False-escalation counts are healthy-case Consult/Urgent assessment-days; they are not unique people. Means exclude missed cases, which are reported separately.</p>
    <details><summary>Configuration, provenance and limitations</summary><p>Specification {data.spec_version}. Source artifact: {data.source_artifact}.</p><p className="pv-hash">Specification fingerprint: {data.spec_sha256}</p><p>{data.crossover}</p><ul>{data.limitations.map(text => <li key={text}>{text}</li>)}</ul></details>
  </section>;
}
