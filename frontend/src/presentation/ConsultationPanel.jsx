import { useEffect, useState } from "react";
import { advanceConsultation, suggestConsultation } from "./consultation.js";
import { measurementsOf } from "./missionModel.js";

const LABELS = {
  suggested: "Consultation suggested", requested: "Consultation requested",
  queued: "Queued for transmission", sent: "Sent from spacecraft",
  delivered: "Delivered to Earth", review_pending: "Ground medical review pending",
  response_prepared: "Simulated response prepared", response_sent: "Response sent to spacecraft",
  response_received: "Response received by crew", closed: "Case acknowledged and closed",
};
const BUTTONS = {
  suggested: "Request consultation", requested: "Queue request", queued: "Transmit to Earth",
  sent: "Receive on Earth", delivered: "Open ground review", review_pending: "Prepare simulated response",
  response_prepared: "Send response to crew", response_sent: "Receive crew response", response_received: "Acknowledge and close",
};

export default function ConsultationPanel({ record, observation, evidenceObservations, cases, onCases, delay, onDelay }) {
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 200);
    return () => clearInterval(timer);
  }, []);
  const visible = cases.filter(c => c.astronautId === record?.astronaut_id && c.day <= record.as_of_day);
  function suggest(outcome, now) {
    onCases(list => [...list, suggestConsultation(record, outcome, evidenceObservations?.[outcome] ?? observation, now, list.length)]);
  }
  return <section className="pv-panel pv-consultations">
    <div className="pv-panel-head"><h2>Synthetic medical consultation</h2></div>
    <p>No real doctor is connected. Operator-selected one-way delay: {delay} simulated minutes (1 second = 1 minute). Ground review is manually simulated.</p>
    <label className="pv-delay"><span>Consultation one-way delay: {delay} min</span>
      <input type="range" min="0" max="20" value={delay} aria-label="Consultation one-way delay"
        onChange={event => onDelay(Number(event.target.value))} /></label>
    <div className="pv-consult-actions">{["sans", "venous"].map(outcome => <button className="pv-btn" type="button" key={outcome}
      disabled={!record || visible.some(c => c.day === record.as_of_day && c.outcome === outcome && c.state !== "closed")}
      onClick={() => suggest(outcome, Date.now())}>Suggest {outcome === "sans" ? "SANS" : "venous"} review</button>)}</div>
    {visible.length === 0 && <p>No consultation has been requested for this visible history.</p>}
    {visible.map(item => {
      const waiting = ["sent", "response_sent"].includes(item.state) && clock < item.arrivesAt;
      const earthDelivered = item.events.some(e => e.state === "delivered");
      const crewReceived = item.events.some(e => e.state === "response_received");
      return <article className="pv-consult-case" key={item.id}>
        <h3>{item.astronautId} · Day {item.day} · {item.outcome.toUpperCase()}</h3>
        <p role="status"><strong>{LABELS[item.state]}</strong>{waiting ? ` · ${Math.ceil((item.arrivesAt - clock) / 1000)} s remaining` : ""}</p>
        <div className="pv-consult-perspectives">
          <div><h4>Crew</h4><p>{item.assessment.tier} · {item.assessment.explanation}</p>
            <p>Requested follow-up: {item.requestedFollowUp}</p>
            <p>{crewReceived ? item.response : "Ground response has not reached the crew."}</p></div>
          <div><h4>Simulated Earth reviewer</h4>{earthDelivered ? <>
            <p>Reason: {item.assessment.tier_reason} · Evidence day {item.assessment.evidence_day ?? "unavailable"}</p>
            <p>{item.assessment.probability == null ? "Probability unavailable" : `${(item.assessment.probability * 100).toFixed(1)}% · ${item.assessment.probability_label}`}</p>
            <p>Evidence packet: {measurementsOf(item.observation).length ? `Observation day ${item.observation.day}; ${measurementsOf(item.observation).map(scan => `${scan.type}; quality ${scan.quality?.status ?? "unknown"}; ${scan.type === "onsd" ? `ONSD ${scan.onsd_mm ?? "unavailable"} mm` : `jugular ${scan.jugular_area_mm2 ?? "unavailable"} mm²; flow ${scan.jugular_flow_class ?? "unavailable"}`}`).join(". ")}` : "No usable scan available in the request packet"}</p>
            {item.response && <p>{item.response}</p>}</> : <p>Request and evidence have not reached Earth.</p>}</div>
        </div>
        {item.state !== "closed" && <button className="pv-btn pv-btn--primary" type="button" disabled={waiting}
          onClick={() => onCases(list => list.map(c => c.id === item.id ? advanceConsultation(c, Date.now(), delay * 1000) : c))}>{BUTTONS[item.state]}</button>}
        <details><summary>Consultation audit trail ({item.events.length} states)</summary><ol>{item.events.map(e => <li key={e.state}>{LABELS[e.state]} · {new Date(e.at).toISOString()}{e.arrivesAt != null ? ` · arrival due ${new Date(e.arrivesAt).toISOString()}` : ""}</li>)}</ol></details>
        <p className="pv-subtle">Closing this communication case does not clear a monitoring alert. Requests are kept for this browser session.</p>
      </article>;
    })}
  </section>;
}
