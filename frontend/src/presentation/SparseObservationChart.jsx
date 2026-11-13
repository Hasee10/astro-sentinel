import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Tabs } from "./WorkspaceUI.jsx";
import { QUALITY_TEXT } from "./constants.js";
import { policyLabel, sparseObservations } from "./missionModel.js";

function MeasurementDot({ cx, cy, payload }) {
  if (!Number.isFinite(payload.value) || cx == null || cy == null) return null;
  return <circle cx={cx} cy={cy} r={payload.quality === "ok" ? 5 : 6}
    fill={payload.quality === "ok" ? "#a2e3ce" : "#14232d"}
    stroke={payload.quality === "ok" ? "#d6fff0" : "#f4c27b"} strokeWidth={2}
    className={`pv-observation-dot pv-observation-${payload.quality}`} data-day={payload.day} />;
}

function MeasurementTooltip({ active, payload, unit, jugular }) {
  const row = payload?.[0]?.payload;
  if (!active || !row || !Number.isFinite(row.value)) return null;
  return <div className="pv-chart-tip">
    <strong>Scan day {row.day}</strong>
    <span>{row.value.toFixed(jugular ? 1 : 2)} {unit} · {QUALITY_TEXT[row.quality] ?? "Quality unknown"}</span>
    {Number.isFinite(row.baseline) && <span>Baseline {row.baseline.toFixed(jugular ? 1 : 2)} {unit}<br />
      Change {(row.value - row.baseline).toFixed(jugular ? 1 : 2)} {unit}{jugular && row.baseline > 0 ? ` (${((row.value / row.baseline - 1) * 100).toFixed(1)}%)` : ""}</span>}
    {jugular && <span>Flow: {row.flow ?? "Not recorded"}</span>}
    <span>Only actual collected observations are shown.</span>
  </div>;
}

export default function SparseObservationChart({ rows, day, missionLength = 30, outcome = "sans", onRecord }) {
  const [view, setView] = useState("connected");
  const jugular = outcome === "venous";
  const unit = jugular ? "mm²" : "mm";
  const name = jugular ? "Jugular area" : "ONSD";
  const series = sparseObservations(rows, day, outcome);
  const { summary } = series;
  const visibleEnd = Math.max(2, Math.min(day, missionLength));
  return <div className="pv-sparse-chart" data-outcome={outcome}>
    <dl className="pv-scan-summary" aria-label={`${name} scan summary`}>
      <div><dt>Actual sessions</dt><dd>{summary.sessions}</dd></div>
      <div><dt>Usable readings</dt><dd>{summary.usable}</dd></div>
      <div><dt>Degraded / failed</dt><dd>{summary.degraded} / {summary.failed}</dd></div>
      <div><dt>Last scan</dt><dd>{summary.lastDay == null ? "None" : `Day ${summary.lastDay}`}</dd></div>
    </dl>
    <p className="pv-chart-policy">{policyLabel(summary.policy)} · through day {day}</p>
    <Tabs label="Observation display" items={[["connected", "Connected trend"], ["points", "Observed points"]]} value={view} onChange={setView} />
    <p className="pv-chart-policy">Measured {name.toLowerCase()} ({unit})</p>
    {series.points.length ? <div className="pv-sparse-plot" role="img"
      aria-label={jugular ? "Jugular area by mission day" : "Optic nerve sheath diameter by mission day"}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series.points} margin={{ top: 18, right: 20, bottom: 16, left: 0 }}>
          <CartesianGrid vertical={false} stroke="#48606b" strokeDasharray="3 5" />
          <XAxis dataKey="day" type="number" domain={[1, visibleEnd]} ticks={[...new Set([1, 5, 10, 15, 20, 25, 30, day].filter(d => d <= day))].sort((a,b) => a-b)}
            tick={{ fill: "#c8dae3", fontSize: 13 }} tickLine={false} label={{ value: "Mission day", position: "insideBottom", offset: -12, fill: "#c8dae3", fontSize: 13 }} />
          <YAxis type="number" domain={[series.low, series.high]} tickCount={5} tickFormatter={v => Number(v).toFixed(jugular ? 0 : 1)} width={52}
            tick={{ fill: "#c8dae3", fontSize: 13 }} tickLine={false} />
          {series.baseline != null && <ReferenceLine y={series.baseline} stroke="#a1b6e3" strokeDasharray="3 4" />}
          <ReferenceLine x={day} stroke="#8aa4ad" strokeDasharray="2 6" />
          {view === "connected" && series.segments.map(segment => <ReferenceLine key={`${segment.from.day}:${segment.to.day}`}
            segment={[{ x: segment.from.day, y: segment.from.value }, { x: segment.to.day, y: segment.to.value }]}
            stroke="#a2e3ce" strokeWidth={2.3} strokeDasharray={segment.gap ? "6 5" : undefined}
            className={segment.gap ? "pv-guide-gap" : "pv-guide-adjacent"} />)}
          <Tooltip content={<MeasurementTooltip unit={unit} jugular={jugular} />} isAnimationActive={false}
            allowEscapeViewBox={{ x: false, y: false }} wrapperStyle={{ maxWidth: "min(300px, 80vw)", zIndex: 5 }} />
          <Line dataKey="value" stroke="none" isAnimationActive={false} dot={<MeasurementDot />} activeDot={{ r: 7, fill: "#a2e3ce" }} />
        </LineChart>
      </ResponsiveContainer>
    </div> : <div className="pv-chart-empty" role="status"><p>No measured {name} values through day {day}.</p>
      <p>{summary.failed ? `${summary.failed} failed acquisition(s) recorded below; no measured Y-value exists.` : "No relevant measurement has been acquired. Nothing is inferred for unscanned days."}</p></div>}
    <ul className="pv-chart-legend" aria-label={`${name} chart legend`}>
      <li><span className="pv-key pv-key-ok" /> Good acquisition</li>
      <li><span className="pv-key pv-key-poor" /> Degraded / quality unknown</li>
      <li><span className="pv-baseline-key" /> Personal baseline {series.baseline == null ? "unavailable" : `${series.baseline.toFixed(jugular ? 1 : 2)} ${unit}`}</li>
      {view === "connected" && <li><span className="pv-guide-key" /> Dashed guides across missing days</li>}
    </ul>
    <p className="pv-chart-note">{view === "connected" ? "Connectors link consecutive usable observations as visual guides. They are not measured or interpolated physiological values." : "Only actual observations are plotted at their recorded mission days."} Failed acquisitions have no Y-value. {jugular ? "Area alone is not a disease diagnosis." : "ONSD alone is not a SANS diagnosis."}</p>
    <div className="pv-failure-rail" aria-label={`${name} failed acquisition rail`}>
      <strong>Failed acquisitions · no measured value</strong>
      {series.samples.filter(row => row.quality === "failed").length ? <div>{series.samples.filter(row => row.quality === "failed").map(row =>
        <button type="button" key={row.day} onClick={() => onRecord?.(row.day)} aria-label={`Open failed ${name} record, day ${row.day}`}><span aria-hidden="true">×</span> Day {row.day}</button>)}</div> : <span>None through day {day}</span>}
    </div>
    <details className="pv-chart-data"><summary>Read actual {name} measurements ({series.samples.length} acquisitions)</summary>
      <div className="pv-table-wrap"><table className="pv-data-table"><caption>Actual {name} scan observations through day {day}</caption>
        <thead><tr><th>Day</th><th>Measured {unit}</th><th>Baseline {unit}</th><th>Quality{jugular ? " / flow" : ""}</th><th>Record</th></tr></thead>
        <tbody>{series.samples.map(row => <tr key={row.day}><td>{row.day}</td><td>{row.value == null ? "No value" : row.value.toFixed(jugular ? 1 : 2)}</td><td>{row.baseline?.toFixed(jugular ? 1 : 2) ?? "Unavailable"}</td><td>{QUALITY_TEXT[row.quality] ?? "Unknown"}{jugular ? ` · ${row.flow ?? "Flow unavailable"}` : ""}</td><td><button type="button" className="pv-text-button" onClick={() => onRecord?.(row.day)}>Day {row.day} record</button></td></tr>)}</tbody>
      </table></div>
    </details>
  </div>;
}
