import test from "node:test";
import assert from "node:assert/strict";
import { CONSULT_STATES, suggestConsultation, advanceConsultation } from "./consultation.js";
import { observationRows, recordPage } from "./missionModel.js";

const record = { astronaut_id: "FIXTURE", as_of_day: 8, sans: {
  tier: "consult", probability: 0.45, explanation: "Explicit engineering evidence",
  recommended_action: { text: "Request simulated ground review" },
} };

test("consultation traverses all ten states with separate delayed request and response", () => {
  let item = suggestConsultation(record, "sans", null, 1000);
  const seen = [item.state];
  let now = 1000;
  while (item.state !== "closed") {
    if (["sent", "response_sent"].includes(item.state)) {
      assert.equal(advanceConsultation(item, item.arrivesAt - 1, 12000), item);
      now = item.arrivesAt;
    }
    item = advanceConsultation(item, now, 12000);
    seen.push(item.state);
  }
  assert.deepEqual(seen, CONSULT_STATES);
  assert.equal(item.events.length, 10);
  assert.match(item.response, /No treatment recommendation/);
  assert.equal(record.sans.tier, "consult", "Closing communication must not clear the assessment");
});

test("consultation snapshots are immutable, outcome-specific and reject future evidence", () => {
  const input = structuredClone(record);
  const item = suggestConsultation(input, "sans", null, 1000);
  input.sans.tier = "monitor";
  assert.equal(item.assessment.tier, "consult");
  assert.throws(() => suggestConsultation(record, "sans", { astronaut_id: "FIXTURE", day: 9 }, 1000), /visible day/);
  assert.throws(() => advanceConsultation(item, 999, 12000), /chronological/);
  assert.throws(() => advanceConsultation(item, 1000, -1), /nonnegative/);
});

test("shared measurements agree with records, preserve units and reveal the selected day", () => {
  const observations = new Map([["FIXTURE:8", { scan_session: { measurements: [
    { type: "onsd", onsd_mm: 5.95, onsd_baseline_mm: 5.35, quality: { status: "degraded" } },
    { type: "jugular", jugular_area_mm2: 68, jugular_baseline_mm2: 34, jugular_flow_class: "stagnant", quality: { status: "ok" } },
  ] } }]]);
  const rows = observationRows(observations, "FIXTURE", 30);
  assert.equal(rows[7].onsd, 5.95);
  assert.equal(rows[7].jugular, 68);
  assert.equal(rows[7].flow, "stagnant");
  assert.equal(rows[7].quality, "degraded");
  assert.equal(rows[6].onsd, null);
  assert.equal(rows[6].jugular, null);
  assert.equal(recordPage(rows, 8, 6), 1);
  assert.equal(recordPage(rows, 29, 6), 4);
});
