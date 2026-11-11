// Presentation-only transforms. Clinical decisions always come from scored data.
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
            record[outcome].tier_reason === "measurement_quality"
              ? "Measurement quality changed. This is not an event detection."
              : record[outcome].explanation,
          key: `${record.as_of_day}:${outcome}`,
        });
    }
    const scan = observations.get(
      `${record.astronaut_id}:${record.as_of_day}`,
    )?.scan;
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

export function chartRange(rows, day) {
  const values = rows
    .filter((row) => row.day <= day && Number.isFinite(row.onsd))
    .map((row) => row.onsd);
  if (!values.length) return null;
  const low = Math.floor((Math.min(...values) - 0.3) * 2) / 2;
  const high = Math.max(
    low + 1,
    Math.ceil((Math.max(...values) + 0.3) * 2) / 2,
  );
  return {
    low,
    high,
    ticks: Array.from(
      { length: Math.round((high - low) * 2) + 1 },
      (_, i) => low + i * 0.5,
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
