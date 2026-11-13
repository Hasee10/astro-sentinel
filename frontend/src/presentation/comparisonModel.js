export function summarizeComparison(report, sensitivity, halfLife) {
  if (report?.validated_for_experiment !== false || !report?.label?.includes("ENGINEERING FIXTURE")) return null;
  const selected = report.rows.filter(row => row.trigger_sensitivity === sensitivity && row.half_life_days === halfLife);
  const result = {};
  for (const policy of ["fixed", "adaptive_replacement"]) {
    const rows = selected.filter(row => row.policy === policy);
    if (!rows.length || rows.length !== report.seeds.length || new Set(rows.map(row => row.seed)).size !== report.seeds.length || rows.some(row => !report.seeds.includes(row.seed))) return null;
    result[policy] = {};
    for (const key of ["sessions", "repeat_sessions", "successful_measurements", "degraded_measurements", "failed_measurements"])
      result[policy][key] = rows.reduce((sum, row) => sum + row[key], 0);
    for (const outcome of ["sans", "venous"]) {
      const detected = rows.reduce((sum, row) => sum + row[outcome].detected_events, 0);
      result[policy][outcome] = {
        detected, missed: rows.reduce((sum, row) => sum + row[outcome].missed_events, 0),
        falseDays: rows.reduce((sum, row) => sum + row[outcome].false_escalation_days, 0),
        delay: detected ? rows.reduce((sum, row) => sum + (row[outcome].mean_detection_delay ?? 0) * row[outcome].detected_events, 0) / detected : null,
      };
    }
  }
  return result;
}
