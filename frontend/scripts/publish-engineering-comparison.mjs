import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Aggregate metrics only. No per-astronaut label, hidden onset or trajectory is
// copied into the website. This never invokes the gated scientific runner.
const source = readFileSync(new URL("../../handoff/research_lead/RECOVERY_ENGINEERING_RESULTS.json", import.meta.url), "utf8");
const report = JSON.parse(source);
if (report.validated_for_experiment !== false || !report.label.includes("ENGINEERING FIXTURE")) throw new Error("Expected explicitly unvalidated engineering results");
const outcome = row => Object.fromEntries(["detected_events", "mean_detection_delay", "missed_events", "false_escalation_days", "falsely_escalated_astronauts", "tier_distribution"].map(key => [key, row[key]]));
const rows = report.rows.map(row => ({
  seed: row.seed, policy: row.policy, days: row.days, crew_size: row.crew_size,
  trigger_sensitivity: row.trigger_sensitivity, half_life_days: row.half_life_days,
  sessions: row.sessions, repeat_sessions: row.repeat_sessions,
  successful_measurements: row.successful_measurements, degraded_measurements: row.degraded_measurements, failed_measurements: row.failed_measurements,
  sans: outcome(row.sans), venous: outcome(row.venous),
}));
const output = { label: report.label, validated_for_experiment: false,
  source_artifact: "RECOVERY_ENGINEERING_RESULTS.json", source_sha256: createHash("sha256").update(source).digest("hex"),
  spec_version: report.spec_version, spec_sha256: report.spec_sha256, seeds: report.seeds,
  cohort_size_per_seed: report.cohort_size_per_seed, rows, metric_definitions: report.metric_definitions,
  limitations: report.limitations, crossover: report.crossover };
const directory = new URL("../public/data/engineering/", import.meta.url);
mkdirSync(directory, { recursive: true });
writeFileSync(new URL("comparison.json", directory), JSON.stringify(output, null, 2) + "\n");
console.log(`Published ${rows.length} labeled aggregate engineering comparison rows to ${fileURLToPath(directory)}. No per-profile ground truth.`);
