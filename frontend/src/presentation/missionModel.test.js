import test from "node:test";
import assert from "node:assert/strict";
import {
  chartRange,
  indexMission,
  reachedEvents,
  recordThrough,
  detailPages,
} from "./missionModel.js";

test("long evidence is paginated without losing words or fabricating content", () => {
  const text = "A recorded measurement is evidence with explicit limitations. "
    .repeat(25)
    .trim();
  const pages = detailPages([{ label: "Explanation", text }], 140);
  assert.ok(pages.length > 1);
  assert.ok(
    pages.every(
      (page) => page.text.length <= 140 && page.label === "Explanation",
    ),
  );
  assert.equal(pages.map((page) => page.text).join(" "), text);
});

const result = (id, day, tier = "unresolved") => ({
  astronaut_id: id,
  as_of_day: day,
  sans: {
    tier,
    tier_reason:
      tier === "repeat"
        ? "measurement_quality"
        : "insufficient_evidence_for_probability",
    explanation: "Recorded explanation",
  },
  venous: { tier: "unresolved" },
});

test("cohort index sorts IDs naturally and preserves every profile and daily record", () => {
  const rows = [
    result("A10", 2),
    result("A2", 1),
    result("A1", 2),
    result("A10", 1),
    result("A1", 1),
  ];
  const indexed = indexMission(rows, [
    { astronaut_id: "A10", day: 1, scan: null },
  ]);
  assert.deepEqual(indexed.ids, ["A1", "A2", "A10"]);
  assert.deepEqual(
    indexed.crew.get("A10").map((row) => row.as_of_day),
    [1, 2],
  );
  assert.equal(indexed.scans.get("A10:1").scan, null);
  assert.equal(rows[0].as_of_day, 2, "input must not be reordered");
});

test("status filtering can only inspect records through the selected day", () => {
  const records = [result("A1", 2), result("A1", 8, "urgent")];
  assert.equal(recordThrough(records, 1), undefined);
  assert.equal(recordThrough(records, 5).sans.tier, "unresolved");
  assert.equal(recordThrough(records, 8).sans.tier, "urgent");
});

test("evidence trail excludes future changes and distinguishes scan quality from detection", () => {
  const records = [result("A1", 1), result("A1", 2, "repeat"), result("A1", 3)];
  const scans = new Map([
    [
      "A1:2",
      { scan: { quality: { status: "failed", reasons: ["No reading"] } } },
    ],
  ]);
  assert.deepEqual(reachedEvents(records, scans, 1), []);
  const events = reachedEvents(records, scans, 2);
  assert.equal(events.length, 2);
  assert.ok(events.every((event) => event.day === 2));
  assert.ok(
    events.some((event) => event.detail.includes("not an event detection")),
  );
});

test("chart axis does not expose future outliers or turn missing readings into zero", () => {
  const rows = [
    { day: 1, onsd: null },
    { day: 2, onsd: 5.6 },
    { day: 3, onsd: 400 },
  ];
  assert.equal(chartRange(rows, 1), null);
  assert.deepEqual(chartRange(rows, 2), {
    low: 5,
    high: 6,
    ticks: [5, 5.5, 6],
  });
  assert.ok(chartRange(rows, 3).high >= 400);
});
