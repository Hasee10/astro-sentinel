import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { OUTCOMES, QUALITY_TEXT } from "./constants.js";
import { OutcomeTile } from "./OutcomeTile.jsx";
import { DetailDialog, Pager, Tabs } from "./WorkspaceUI.jsx";
import { usePageSize } from "./usePageSize.js";

export function OutcomeGroup({ record }) {
  const [outcome, setOutcome] = useState("sans");
  return (
    <div className="pv-outcome-group">
      <div className="pv-outcome-switch">
        <Tabs
          label="Monitoring outcome"
          items={OUTCOMES.map((meta) => [meta.key, meta.name])}
          value={outcome}
          onChange={setOutcome}
        />
      </div>
      <div className="pv-tiles" data-outcome={outcome}>
        {OUTCOMES.map((meta) => (
          <div className={`pv-outcome-slot pv-slot-${meta.key}`} key={meta.key}>
            <OutcomeTile meta={meta} outcome={record?.[meta.key]} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function EventPanel({ events, day, onJump }) {
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState(null);
  const { ref, size } = usePageSize(100, 110, 4);
  const count = Math.max(1, Math.ceil(events.length / size));
  const current = Math.min(page, count - 1);
  return (
    <section className="pv-panel pv-paged-panel" ref={ref}>
      <div className="pv-panel-head">
        <h2>Recorded changes</h2>
        <span className="pv-subtle">Through day {day}</span>
      </div>
      <div className="pv-event-rows">
        {events.length ? (
          events.slice(current * size, (current + 1) * size).map((event) => (
            <article className="pv-event-row" key={event.key}>
              <button
                type="button"
                className="pv-event-day"
                onClick={() => onJump(event.day)}
                aria-label={`Go to day ${event.day}`}
              >
                Day {event.day}
              </button>
              <div>
                <h3>{event.title}</h3>
                <p>{event.detail}</p>
              </div>
              <button
                className="pv-icon-button"
                type="button"
                aria-label={`Read ${event.title}, day ${event.day}`}
                onClick={() => setDetail(event)}
              >
                <Icon name="external" size={18} />
              </button>
            </article>
          ))
        ) : (
          <div className="pv-empty-state">
            <Icon name="timeline" size={34} />
            <h3>No changes yet</h3>
            <p>Continue playback to follow incoming evidence.</p>
          </div>
        )}
      </div>
      <Pager
        page={current}
        count={count}
        onChange={setPage}
        label="Change pages"
      />
      {detail && (
        <DetailDialog
          title={`Day ${detail.day} · ${detail.title}`}
          entries={[{ label: "Recorded change", text: detail.detail }]}
          onClose={() => setDetail(null)}
        />
      )}
    </section>
  );
}

export function ObservationPanel({ rows, day, astronautId }) {
  const [page, setPage] = useState(0);
  const { ref, size } = usePageSize(42, 170, 10);
  const reached = rows.filter((row) => row.day <= day);
  const count = Math.max(1, Math.ceil(reached.length / size));
  const current = Math.min(page, count - 1);
  return (
    <section className="pv-panel pv-paged-panel" ref={ref}>
      <div className="pv-panel-head">
        <h2>Observation record</h2>
        <span className="pv-subtle">
          {astronautId} · through day {day}
        </span>
      </div>
      <table className="pv-data-table">
        <thead>
          <tr>
            <th>Day</th>
            <th>ONSD</th>
            <th>Quality</th>
          </tr>
        </thead>
        <tbody>
          {reached.slice(current * size, (current + 1) * size).map((row) => (
            <tr key={row.day}>
              <td>{row.day}</td>
              <td>
                {row.onsd === null
                  ? "Unavailable"
                  : `${row.onsd.toFixed(2)} mm`}
              </td>
              <td>{QUALITY_TEXT[row.quality] ?? "No scan"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="pv-subtle">
        Failed values are excluded. Future records stay hidden.
      </p>
      <Pager
        page={current}
        count={count}
        onChange={setPage}
        label="Observation pages"
      />
    </section>
  );
}

export function TransmissionPanel({ messages, now }) {
  const [page, setPage] = useState(0);
  const { ref, size } = usePageSize(78, 110, 5);
  const count = Math.max(1, Math.ceil(messages.length / size));
  const current = Math.min(page, count - 1);
  return (
    <section className="pv-panel pv-paged-panel" ref={ref}>
      <div className="pv-panel-head">
        <h2>Transmission history</h2>
        <span className="pv-subtle">{messages.length} messages</span>
      </div>
      <div className="pv-transmission-rows">
        {messages.length ? (
          [...messages]
            .reverse()
            .slice(current * size, (current + 1) * size)
            .map((message) => (
              <div key={message.id}>
                <Icon
                  name={message.dir === "up" ? "send" : "check"}
                  size={20}
                />
                <div>
                  <strong>
                    {message.dir === "up" ? "Crew → Earth" : "Earth → Crew"}
                  </strong>
                  <p>Mission day {message.day}</p>
                </div>
                <span>
                  {message.arrivesAt <= now ? "Delivered" : "In transit"}
                </span>
              </div>
            ))
        ) : (
          <div className="pv-empty-state">
            <Icon name="send" size={34} />
            <h3>No transmissions yet</h3>
            <p>Use the Send update tab to share a snapshot.</p>
          </div>
        )}
      </div>
      <Pager
        page={current}
        count={count}
        onChange={setPage}
        label="Transmission pages"
      />
    </section>
  );
}

export function ResearchPanel({ manifest, evaluation, tab }) {
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState(null);
  const { ref, size } = usePageSize(62, 110, 6);
  const blockers = evaluation?.blockers ?? [];
  const capabilities = Object.entries(manifest?.capability_readiness ?? {});
  const source = tab === "blockers" ? blockers : capabilities;
  const count = Math.max(1, Math.ceil(source.length / size));
  const current = Math.min(page, count - 1);
  const label = (text) =>
    text
      .replaceAll("_", " ")
      .replace(/\b(sans|onsd|hrv|ptt)\b/gi, (word) => word.toUpperCase());
  if (tab === "summary")
    return (
      <section className="pv-panel pv-research-summary" ref={ref}>
        <div className="pv-panel-head">
          <h2>Research readiness</h2>
          <span className="pv-tag">Synthetic demonstration</span>
        </div>
        <div className="pv-research-status">
          <Icon name="research" size={28} />
          <div>
            <h3>
              {evaluation
                ? blockers.length
                  ? "Scientific comparison blocked"
                  : "No blockers reported"
                : "Readiness report unavailable"}
            </h3>
            <p>
              {blockers.length
                ? "Monitoring views are available. Experimental results require additional models and decisions."
                : "This workspace displays a readiness report; it does not display comparison results."}
            </p>
          </div>
        </div>
        <dl>
          <div>
            <dt>Generation</dt>
            <dd>
              {manifest?.generation_status?.replaceAll("_", " ") ??
                "Unavailable"}
            </dd>
          </div>
          <div>
            <dt>Independent outcomes</dt>
            <dd>SANS and venous</dd>
          </div>
          <div>
            <dt>Available capabilities</dt>
            <dd>
              {capabilities.filter(([, status]) => status === "ready").length}{" "}
              of {capabilities.length}
            </dd>
          </div>
        </dl>
        <p className="pv-subtle">
          Missing probabilities remain unavailable. Quality-related Repeat is
          not evidence of a detected physiological event.
        </p>
      </section>
    );
  if (tab === "provenance") {
    const entries = Object.entries({
      "Run ID": manifest?.run_id,
      Schema: manifest?.schema_version,
      "Random seed": manifest?.random_seed,
      "Synthetic profiles": manifest?.crew_size,
      "Mission window": `${manifest?.mission_duration_days ?? "—"} days`,
      "Created at": manifest?.created_at,
    });
    const pages = Math.max(1, Math.ceil(entries.length / size));
    const selected = Math.min(page, pages - 1);
    return (
      <section className="pv-panel pv-run-info" ref={ref}>
        <div className="pv-panel-head">
          <h2>Run provenance</h2>
        </div>
        <dl>
          {entries
            .slice(selected * size, (selected + 1) * size)
            .map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value ?? "Unavailable"}</dd>
              </div>
            ))}
        </dl>
        <Pager
          page={selected}
          count={pages}
          onChange={setPage}
          label="Provenance pages"
        />
      </section>
    );
  }
  return (
    <section className="pv-panel pv-paged-panel" ref={ref}>
      <div className="pv-panel-head">
        <h2>
          {tab === "blockers"
            ? "Evaluation blockers"
            : "Generation capabilities"}
        </h2>
        <span className="pv-subtle">{source.length} items</span>
      </div>
      <div className="pv-research-rows">
        {source.slice(current * size, (current + 1) * size).map((item) =>
          tab === "blockers" ? (
            <button
              type="button"
              key={item.capability}
              onClick={() =>
                setDetail({ title: label(item.capability), text: item.message })
              }
            >
              <Icon name="info" size={18} />
              <span>{label(item.capability)}</span>
              <Icon name="external" size={17} />
            </button>
          ) : (
            <button
              type="button"
              key={item[0]}
              onClick={() =>
                setDetail({
                  title: label(item[0]),
                  text:
                    manifest?.physiological_generation_blocked_reasons?.[
                      item[0]
                    ] ?? `Capability status: ${label(item[1])}.`,
                })
              }
            >
              <span>{label(item[0])}</span>
              <span className={item[1] === "ready" ? "is-ready" : "pv-waiting"}>
                {item[1] === "ready" ? "Ready" : "Blocked"}
              </span>
              <Icon name="external" size={17} />
            </button>
          ),
        )}
      </div>
      <Pager
        page={current}
        count={count}
        onChange={setPage}
        label={`${tab === "blockers" ? "Blocker" : "Capability"} pages`}
      />
      {detail && (
        <DetailDialog
          title={detail.title}
          entries={[{ label: "Backend readiness report", text: detail.text }]}
          onClose={() => setDetail(null)}
        />
      )}
    </section>
  );
}
