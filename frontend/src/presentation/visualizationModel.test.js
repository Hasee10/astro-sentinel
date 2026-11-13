import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { evidenceFor, indexMission, nextEvidenceAction, observationRows, sparseObservations } from "./missionModel.js";
import { summarizeComparison } from "./comparisonModel.js";

const rows = [
  { day: 1, onsd: 5.1, baseline: 5, quality: "ok", hasSession: true },
  { day: 2, onsd: null, quality: null, hasSession: false },
  { day: 3, onsd: 999, quality: "failed", hasSession: true },
  { day: 8, onsd: 5.7, baseline: 5, quality: "degraded", hasSession: true },
  { day: 10, onsd: 42, baseline: 5, quality: "ok", hasSession: true },
];
test("sparse connectors preserve actual days, exclude failed values and never generate daily readings", () => {
  const series = sparseObservations(rows, 8);
  assert.deepEqual(series.points.map(row => [row.day, row.value]), [[1, 5.1], [8, 5.7]]);
  assert.equal(series.segments.length, 1);
  assert.equal(series.segments[0].gap, true);
  assert.equal(series.segments[0].from.day, 1);
  assert.equal(series.segments[0].to.day, 8);
  assert.equal(series.samples.find(row => row.day === 3).value, null);
  assert.equal(series.summary.sessions, 3);
  assert.equal(series.summary.failed, 1);
  assert.equal(series.summary.degraded, 1);
  assert.ok(series.high < 42);
});
test("zero, one, and only-failed acquisitions retain honest empty/point states", () => {
  assert.equal(sparseObservations([], 30).points.length, 0);
  assert.equal(sparseObservations(rows, 1).segments.length, 0);
  const failed = sparseObservations([rows[2]], 3);
  assert.equal(failed.points.length, 0);
  assert.equal(failed.summary.failed, 1);
  assert.equal(failed.samples[0].day, 3);
});
test("independent jugular evidence preserves baseline, area, flow, quality and visible day", () => {
  const jugular = [{ day: 1, jugular: 34, jugularBaseline: 34, flow: "antegrade", jugularQuality: "ok", hasSession: true },
    { day: 8, jugular: 68, jugularBaseline: 34, flow: "retrograde", jugularQuality: "degraded", hasSession: true }];
  assert.equal(evidenceFor(jugular, 1, "venous").latestUsable.value, 34);
  const latest = evidenceFor(jugular, 8, "venous").latestUsable;
  assert.equal(latest.flow, "retrograde");
  assert.equal(latest.baseline, 34);
  assert.equal(evidenceFor(jugular, 8, "sans").points.length, 0);
});
test("real E4 preview and evidence cards share one coherent observed run and day", () => {
  const base = new URL("../../public/data/fixtures/recovery/", import.meta.url);
  const load = name => readFileSync(new URL(name, base), "utf8").trim().split(/\r?\n/).map(JSON.parse);
  const observations = load("crew_observations.jsonl"), assessments = load("crew_scored.jsonl");
  const indexed = indexMission(assessments, observations);
  const assessment = indexed.crew.get("E4").find(r => r.as_of_day === 14);
  const observation = indexed.scans.get("E4:14");
  assert.equal(assessment.run_id, observation.metadata.run_id);
  const profileRows = observationRows(indexed.scans, "E4", 30);
  assert.equal(evidenceFor(profileRows, 14, "sans").latestUsable.value, observation.scan_session.measurements.find(m => m.type === "onsd").onsd_mm);
  assert.equal(assessment.sans.tier, "consult");
  assert.ok(assessment.sans.probability_label.includes("ENGINEERING FIXTURE"));
  const other = observationRows(indexed.scans, "E1", 30);
  assert.notEqual(evidenceFor(other, 14, "sans").latestUsable.value, evidenceFor(profileRows, 14, "sans").latestUsable.value);
});
test("next acquisition wording uses approved anchors or declared targets, not future observations", () => {
  assert.match(nextEvidenceAction({}, 8, "fixed_7_day_day1_anchor"), /day 15/);
  assert.match(nextEvidenceAction({}, 8, "adaptive_replacement"), /pending/);
  assert.match(nextEvidenceAction({ recommended_action: { follow_up_day: 10, follow_up_rule: "Within 2 days" } }, 8, "adaptive_replacement"), /not a confirmed future acquisition/);
});
test("engineering comparison displays actual aggregate results and refuses validated-science relabeling", () => {
  const report = JSON.parse(readFileSync(new URL("../../public/data/engineering/comparison.json", import.meta.url), "utf8"));
  const totals = summarizeComparison(report, 0.7, 7);
  assert.equal(totals.fixed.sessions, 1068);
  assert.equal(totals.adaptive_replacement.sessions, 1579);
  assert.equal(totals.fixed.sans.missed, 2);
  assert.equal(totals.adaptive_replacement.sans.missed, 9);
  assert.equal(summarizeComparison({ ...report, validated_for_experiment: true }, 0.7, 7), null);
});
