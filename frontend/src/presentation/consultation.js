// Synthetic coordination only. Delays are explicit operator-selected demo
// settings, not an approved communication-distribution research assumption.
export const CONSULT_STATES = ["suggested", "requested", "queued", "sent", "delivered",
  "review_pending", "response_prepared", "response_sent", "response_received", "closed"];

export function suggestConsultation(record, outcome, observation, now, sequence = 0) {
  if (!record?.[outcome]) throw new Error("A recorded assessment is required");
  if (observation && (observation.astronaut_id !== record.astronaut_id || observation.day > record.as_of_day))
    throw new Error("Consultation evidence must belong to this profile and visible day");
  return {
    id: `${record.astronaut_id}:${record.as_of_day}:${outcome}:${now}:${sequence}`,
    astronautId: record.astronaut_id, day: record.as_of_day, outcome,
    state: "suggested", synthetic: true,
    assessment: structuredClone(record[outcome]),
    observation: observation ? structuredClone(observation) : null,
    requestedFollowUp: record[outcome].recommended_action?.text ?? "Review available evidence and monitoring limitations",
    events: [{ state: "suggested", at: now }],
  };
}

export function advanceConsultation(item, now, delayMs) {
  if (!Number.isFinite(now) || now < item.events.at(-1).at || !Number.isFinite(delayMs) || delayMs < 0)
    throw new Error("Consultation clock and delay must be nonnegative and chronological");
  const index = CONSULT_STATES.indexOf(item.state);
  if (index < 0 || index === CONSULT_STATES.length - 1) return item;
  if (["sent", "response_sent"].includes(item.state) && now < item.arrivesAt) return item;
  const state = CONSULT_STATES[index + 1];
  const next = { ...item, state, events: [...item.events, { state, at: now }] };
  if (["sent", "response_sent"].includes(state)) {
    next.arrivesAt = now + delayMs;
    next.events.at(-1).arrivesAt = next.arrivesAt;
  }
  if (state === "response_prepared") next.response =
    "SIMULATED GROUND REVIEW: Evidence packet received. Review measurement quality and model limitations with the simulated crew medical officer. Follow-up timing remains subject to the approved policy. No treatment recommendation is generated.";
  return next;
}
