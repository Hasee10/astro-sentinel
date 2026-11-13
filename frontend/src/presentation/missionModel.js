// Presentation-only transforms. Clinical decisions always come from scored data.
export function measurementsOf(observation) {
  return observation?.scan_session?.measurements ?? (observation?.scan ? [observation.scan] : []);
}
export function indexMission(scored, observations = []) {
  const crew = new Map();
  const scans = new Map();
  for (const record of scored) {
    if (!crew.has(record.astronaut_id)) crew.set(record.astronaut_id, []);
    crew.get(record.astronaut_id).push(record);
  }
  for (const records of crew.values())
    records.sort((a, b) => a.as_of_day - b.as_of_day);
  for (const observation of observations)
    scans.set(`${observation.astronaut_id}:${observation.day}`, observation);
  return {
    crew,
    scans,
    ids: [...crew.keys()].sort((a, b) =>
      a.localeCompare(b, undefined, { numeric: true }),
    ),
  };
}

export function recordThrough(records, day) {
  return records.findLast((record) => record.as_of_day <= day);
}

export function reachedEvents(records, observations, day) {
  const events = [];
  for (let i = 0; i < records.length; i += 1) {
    const record = records[i];
    if (record.as_of_day > day) break;
    const previous = records[i - 1];
    for (const outcome of ["sans", "venous"]) {
      if (previous && previous[outcome].tier !== record[outcome].tier)
        events.push({
          day: record.as_of_day,
          title: `${outcome === "sans" ? "SANS" : "Venous"} · ${record[outcome].tier}`,
          detail:
            record[outcome].recommended_action
              ? `${record[outcome].explanation} Next: ${record[outcome].recommended_action.text} Follow-up: ${record[outcome].recommended_action.follow_up_rule}.`
              : record[outcome].tier_reason === "measurement_quality"
              ? "Measurement quality changed. This is not an event detection."
              : record[outcome].explanation,
          key: `${record.as_of_day}:${outcome}`,
          action: record[outcome].recommended_action,
        });
    }
    const observation = observations.get(`${record.astronaut_id}:${record.as_of_day}`);
    const measurements = measurementsOf(observation);
    if (observation?.scan_session || measurements.some(m => m.type)) events.push({
      day: record.as_of_day, title: "Ultrasound session acquired",
      detail: `Policy: ${observation.metadata?.acquisition_policy ?? "not recorded"}. Scheduling reason: ${observation.metadata?.scheduling_reason ?? "not recorded"}. ${measurements.map(m => `${m.type}: ${m.type === "onsd" ? `${m.onsd_mm ?? "unavailable"} mm` : `${m.jugular_area_mm2 ?? "unavailable"} mm²; flow ${m.jugular_flow_class ?? "unavailable"}`}; quality ${m.quality?.status ?? "unknown"}`).join(". ")}`,
      key: `${record.as_of_day}:acquisition`,
    });
    const triggers = Object.entries(observation?.metadata?.observable_triggers ?? {}).filter(([, flag]) => flag);
    if (triggers.length) events.push({ day: record.as_of_day, title: "Observable scheduling trigger",
      detail: `${triggers.map(([outcome]) => outcome.toUpperCase()).join(" + ")} trigger observed. Decision: ${observation.metadata.scheduling_reason}. A trigger is not a diagnosis.`, key: `${record.as_of_day}:trigger` });
    if (observation?.metadata?.scheduling_reason === "routine_deferred") events.push({ day: record.as_of_day,
      title: "Routine session deferred", detail: "The current policy deferred routine acquisition using available history. The maximum-gap backstop remains active.", key: `${record.as_of_day}:deferral` });
    const scan = measurementsOf(observation).find(s => ["failed", "degraded", "unknown"].includes(s.quality?.status));
    if (
      scan &&
      ["failed", "degraded", "unknown"].includes(scan.quality?.status)
    )
      events.push({
        day: record.as_of_day,
        title: `Scan quality · ${scan.quality.status}`,
        detail:
          scan.quality.reasons?.join(" · ") ||
          "Quality issue recorded by the backend.",
        key: `${record.as_of_day}:quality`,
      });
  }
  return events.reverse();
}

export function observationRows(observations, astronautId, length) {
  return Array.from({ length }, (_, i) => {
    const observation = observations.get(`${astronautId}:${i + 1}`);
    const measurements = measurementsOf(observation);
    const scan = measurements.find(m => m.type === "onsd");
    const jugularScan = measurements.find(m => m.type === "jugular");
    const usableValue = scan?.quality?.status !== "failed";
    return { day: i + 1,
      onsd: scan?.type === "onsd" && usableValue ? scan.onsd_mm ?? null : null,
      baseline: scan?.onsd_baseline_mm ?? null,
      jugular: jugularScan?.quality?.status !== "failed" ? jugularScan?.jugular_area_mm2 ?? null : null,
      jugularBaseline: jugularScan?.jugular_baseline_mm2 ?? null,
      jugularQuality: jugularScan?.quality?.status ?? null,
      flow: jugularScan?.jugular_flow_class ?? null,
      quality: scan?.quality?.status ?? null,
      policy: observation?.metadata?.acquisition_policy,
      schedulingReason: observation?.metadata?.scheduling_reason,
    };
  });
}

export function recordPage(rows, day, size) {
  const index = rows.filter(r => r.day <= day).findIndex(r => r.day === day);
  return Math.floor(Math.max(0, index) / size);
}

export function chartRange(rows, day, step = 0.5) {
  const values = rows
    .filter((row) => row.day <= day && Number.isFinite(row.onsd))
    .map((row) => row.onsd);
  if (!values.length) return null;
  const low = Math.floor((Math.min(...values) - 0.3) / step) * step;
  const high = Math.max(
    low + step * 2,
    Math.ceil((Math.max(...values) + 0.3) / step) * step,
  );
  return {
    low,
    high,
    ticks: Array.from(
      { length: Math.round((high - low) / step) + 1 },
      (_, i) => low + i * step,
    ),
  };
}

export function detailPages(entries, limit = 360) {
  return entries.flatMap(({ label, text }) => {
    const pages = [];
    let part = "";
    for (const word of String(text ?? "Unavailable").split(/\s+/)) {
      if (part && part.length + word.length + 1 > limit) {
        pages.push({ label, text: part });
        part = "";
      }
      part += `${part ? " " : ""}${word}`;
    }
    if (part) pages.push({ label, text: part });
    return pages;
  });
}
