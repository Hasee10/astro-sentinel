import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useState } from "react";
import { Tabs } from "./WorkspaceUI.jsx";
import { OUTCOMES, QUALITY_TEXT, TIER_TEXT, TIERS } from "./constants.js";
import { chartRange } from "./missionModel.js";

const POOR = ["degraded", "unknown"];

// A dot on the ONSD line: solid for a good scan, hollow amber for a poor one.
function OnsdDot({ cx, cy, payload }) {
  if (payload.onsd === null || cx === undefined) return null;
  if (POOR.includes(payload.quality)) {
    return <circle cx={cx} cy={cy} r={4.5} className="pv-dot-poor" />;
  }
  return <circle cx={cx} cy={cy} r={3.5} className="pv-dot-ok" />;
}

// A small cross at the bottom of the chart for a failed scan (no value).
function FailedMark({ cx, cy, payload }) {
  if (payload.failedY === null || cx === undefined) return null;
  return (
    <g className="pv-dot-failed">
      <line x1={cx - 4} y1={cy - 4} x2={cx + 4} y2={cy + 4} />
      <line x1={cx - 4} y1={cy + 4} x2={cx + 4} y2={cy - 4} />
    </g>
  );
}

// The hover line, which stays away from days that haven't been reached.
function DayCursor({ points, payload }) {
  if (!points?.length || payload?.[0]?.payload?.isFuture) return null;
  const [from, to] = points;
  return (
    <line
      x1={from.x}
      y1={from.y}
      x2={to.x}
      y2={to.y}
      className="pv-chart-cursor"
    />
  );
}

function OnsdTooltip({ active, payload, unit = "mm" }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  if (row.isFuture) return null;
  return (
    <div className="pv-chart-tip">
      <strong>Day {row.day}</strong>
      <span>
        {row.onsd === null ? "Unavailable" : `${row.onsd.toFixed(2)} ${unit}`}
      </span>
      <span>
        {row.quality ? (QUALITY_TEXT[row.quality] ?? row.quality) : "No scan"}
      </span>
    </div>
  );
}

// The ONSD values for one astronaut up to the current day, with that day marked.
// The axes stay fixed, so the line grows from left to right.
function OnsdChart({ rows, range, day, jugular = false }) {
  // This checks every day, so a failed first scan doesn't read as "no scans".
  const reached = rows.filter((row) => row.day <= day);
  const hasScans = reached.some(
    (row) => row.onsd !== null || row.quality === "failed",
  );
  if (!range || !hasScans) {
    const failed = reached.filter((row) => row.quality === "failed").length;
    return (
      <div className="pv-chart-empty">
        <p>No usable {jugular ? "jugular" : "ONSD"} values through day {day}.</p>
        <small>
          {failed
            ? `${failed} failed scan(s) recorded. Failed values are never plotted.`
            : "New observations appear as the mission advances."}
        </small>
      </div>
    );
  }
  const { low, high, ticks } = range;
  // A later day keeps its place on the axis but holds no scan data at all.
  const data = rows.map((row) =>
    row.day > day
      ? {
          day: row.day,
          isFuture: true,
          onsd: null,
          quality: null,
          failedY: null,
        }
      : { ...row, failedY: row.quality === "failed" ? low : null },
  );

  return (
    <div
      className="pv-chart"
      role="img"
      aria-label={jugular ? "Jugular area by mission day" : "Optic nerve sheath diameter by mission day"}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 4, left: -8 }}
        >
          <CartesianGrid
            vertical={false}
            stroke="#263b48"
            strokeOpacity={0.65}
            strokeDasharray="3 5"
          />
          <XAxis
            dataKey="day"
            type="number"
            domain={[1, rows.length]}
            ticks={[1, 5, 10, 15, 20, 25, 30].filter((t) => t <= rows.length)}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            domain={[low, high]}
            ticks={ticks}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => v.toFixed(1)}
            width={44}
          />
          {/* filterNull={false} keeps every row in the tooltip's data, so it can
              tell a later day from an earlier day with no scan. */}
          <Tooltip
            content={<OnsdTooltip unit={jugular ? "mm²" : "mm"} />}
            cursor={<DayCursor />}
            filterNull={false}
            isAnimationActive={false}
          />
          <ReferenceLine
            x={day}
            stroke="#5f8c8d"
            strokeDasharray="3 5"
            ifOverflow="extendDomain"
          />
          <Line
            dataKey="onsd"
            stroke="#a0d9cf"
            strokeWidth={2}
            type="linear"
            connectNulls={false}
            isAnimationActive={false}
            dot={<OnsdDot />}
            activeDot={false}
          />
          <Line
            dataKey="failedY"
            stroke="none"
            isAnimationActive={false}
            dot={<FailedMark />}
            activeDot={false}
            legendType="none"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Two rows of 30 days, one per outcome, coloured by that outcome's tier. Days after
// the current day are empty and can't be clicked, and their tier is never read.
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

export function TrendsPanel({
  astronautId,
  records,
  onsdRows,
  onsdRange,
  missionLength,
  day,
  onJump,
  expanded = false,
}) {
  const [mode, setMode] = useState("trace");
  const reachedCount = onsdRows.filter(
    (row) => row.day <= day && row.onsd !== null,
  ).length;
  return (
    <section className="pv-panel pv-trends" aria-labelledby="pv-trends-title">
      <header className="pv-panel-head">
        <div>
          <span className="pv-eyebrow">OBSERVATION HISTORY</span>
          <h2 id="pv-trends-title">{mode === "jugular" ? "Jugular area over time" : "ONSD over time"}</h2>
        </div>
        <span className="pv-subtle">
          {astronautId} · through day {day}
        </span>
      </header>
      <Tabs
        label="Chart views"
        items={[
          ["trace", "ONSD trace"],
          ["jugular", "Jugular trace"],
          ["tiers", "Tier history"],
        ]}
        value={mode}
        onChange={setMode}
      />
      <div className="pv-trends-grid">
        {mode === "jugular" && <div className="pv-trace-view">
          <h3 className="pv-sub">Jugular cross-sectional area (mm²)</h3>
          <OnsdChart rows={onsdRows.map(r => ({ ...r, onsd: r.jugular, quality: r.jugularQuality }))}
            range={chartRange(onsdRows.map(r => ({ ...r, onsd: r.jugular })), day, 10)} day={day} jugular />
          <p>Area is a measurement, not a disease threshold. No scans are inferred on unscheduled days.</p>
        </div>}
        {mode === "trace" && (
          <div className="pv-trace-view">
            <h3 className="pv-sub">Optic nerve sheath diameter (mm)</h3>
            <OnsdChart rows={onsdRows} range={onsdRange} day={day} />
            <p className="pv-footnote">
              <span className="pv-key pv-key-ok" /> scan
              <span className="pv-key pv-key-poor" /> poor quality
              <span className="pv-key pv-key-failed">×</span> failed scan
            </p>
            <p className="pv-trend-note">
              {reachedCount === 1
                ? "One observation available. Continue playback to build the trace."
                : `${reachedCount} recorded values shown.`}{" "}
              {expanded
                ? "No personal baseline band or clinical threshold is inferred."
                : "Future observations remain hidden."}
            </p>
          </div>
        )}
        {mode === "tiers" && (
          <div className="pv-strip-section">
            <h3 className="pv-sub">Decision tier by day</h3>
            <TierStrip
              records={records}
              missionLength={missionLength}
              day={day}
              onJump={onJump}
            />
          </div>
        )}
      </div>
    </section>
  );
}
