import { useState } from "react";
import { Tabs } from "./WorkspaceUI.jsx";
import { OUTCOMES, TIER_TEXT, TIERS } from "./constants.js";
import SparseObservationChart from "./SparseObservationChart.jsx";

function TierStrip({ records, missionLength, day, onJump }) {
  const byDay = new Map(records.map((record) => [record.as_of_day, record]));
  const days = Array.from({ length: missionLength }, (_, i) => i + 1);
  return (
    <div className="pv-strip">
      {OUTCOMES.map((meta) => (
        <div className="pv-strip-row" key={meta.key}>
          <span className="pv-strip-name">{meta.name}</span>
          <div className="pv-strip-days">
            {days.map((d) => {
              if (d > day) {
                const text = `Day ${d}: not yet reached`;
                return (
                  <button
                    key={d}
                    type="button"
                    className="pv-day pv-day--future"
                    disabled
                    aria-label={text}
                    title={text}
                  />
                );
              }
              const record = byDay.get(d);
              const tier = record?.[meta.key]?.tier;
              return (
                <button
                  key={d}
                  type="button"
                  className={`pv-day ${tier ? `pv-tier-${tier}` : "pv-day--none"}${d === day ? " is-today" : ""}`}
                  disabled={!record}
                  onClick={() => onJump(d)}
                  aria-label={`Day ${d}: ${tier ? (TIER_TEXT[tier]?.label ?? tier) : "no record"}`}
                  title={`Day ${d}: ${tier ? (TIER_TEXT[tier]?.label ?? tier) : "no record"}`}
                />
              );
            })}
          </div>
        </div>
      ))}
      <div className="pv-strip-labels">
        <span>DAY 01</span>
        <span>DAY {missionLength}</span>
      </div>
      <div className="pv-legend">
        {TIERS.map((tier) => (
          <span key={tier} className={`pv-legend-item pv-tier-${tier}`}>
            {TIER_TEXT[tier].label}
          </span>
        ))}
        <span className="pv-legend-item pv-legend-future">Not yet reached</span>
      </div>
    </div>
  );
}

export function TrendsPanel({ astronautId, records, onsdRows, missionLength, day, onJump, onRecord }) {
  const [mode, setMode] = useState("trace");
  return <section className="pv-panel pv-trends" aria-labelledby="pv-trends-title">
    <header className="pv-panel-head"><div><span className="pv-eyebrow">Observation history</span>
      <h2 id="pv-trends-title">{mode === "jugular" ? "Jugular area over time" : mode === "tiers" ? "Monitoring tier history" : "ONSD over time"}</h2></div>
      <span className="pv-subtle">{astronautId} · through day {day}</span></header>
    <Tabs label="Chart views" items={[["trace", "ONSD trace"], ["jugular", "Jugular trace"], ["tiers", "Tier history"]]} value={mode} onChange={setMode} />
    {mode === "tiers" ? <TierStrip records={records} missionLength={missionLength} day={day} onJump={onJump} />
      : <SparseObservationChart rows={onsdRows} day={day} missionLength={missionLength} outcome={mode === "jugular" ? "venous" : "sans"} onRecord={onRecord ?? onJump} />}
  </section>;
}
