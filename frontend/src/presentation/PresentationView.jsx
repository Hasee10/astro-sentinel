import { useCallback, useEffect, useMemo, useState } from "react";
import Icon from "../components/Icon.jsx";
import {
  ACTION_TIERS,
  DEFAULT_DELAY_MINUTES,
  EXPECTED_SCHEMA_VERSION,
  FALLBACK_MISSION_LENGTH,
  MAX_DELAY_MINUTES,
  MS_PER_DAY,
  MS_PER_MISSION_MINUTE,
  OUTCOMES,
  QUALITY_TEXT,
  SPEEDS,
} from "./constants.js";
import Logo from "../components/Logo.jsx";
import CohortBrowser from "./CohortBrowser.jsx";
import { Dialog, Tabs } from "./WorkspaceUI.jsx";
import {
  OutcomeGroup,
  EventPanel,
  ObservationPanel,
  TransmissionPanel,
  ResearchPanel,
} from "./WorkspacePanels.jsx";
import { TrendsPanel } from "./TrendsPanel.jsx";
import { useMissionData } from "./useMissionData.js";
import { chartRange, indexMission, reachedEvents, observationRows, measurementsOf } from "./missionModel.js";
import ConsultationPanel from "./ConsultationPanel.jsx";
import "./presentation.css";

const VIEWS = [
  { id: "dashboard", label: "Overview", icon: "grid" },
  { id: "ground", label: "Earth link", icon: "signal" },
  { id: "timeline", label: "Timeline", icon: "timeline" },
  { id: "research", label: "Research", icon: "research" },
];
const TITLES = {
  dashboard: ["Mission overview", "An independent view of every observation."],
  ground: ["Earth link", "What the crew knows. What Earth has received."],
  timeline: [
    "Mission timeline",
    "Follow the evidence, one mission day at a time.",
  ],
  research: [
    "Research & readiness",
    "A transparent view of what this simulation can support.",
  ],
};

function countdown(ms) {
  const seconds = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function tierChange(previous, record) {
  if (!previous || !record) return null;
  const changes = OUTCOMES.filter(
    ({ key }) => previous[key].tier !== record[key].tier,
  );
  return changes.length
    ? changes
        .map(
          ({ key, name }) =>
            `${name}: ${previous[key].tier} → ${record[key].tier}`,
        )
        .join(" · ")
    : null;
}

export default function PresentationView(props) {
  const data = useMissionData(props.engineeringFixture);
  if (data.status !== "ready")
    return (
      <div className="pv pv-loading">
        <a href="#" className="pv-brand">
          <Logo /> ASTROSENTINEL
        </a>
        <div className="pv-loading-card">
          <Icon name={data.status === "error" ? "info" : "signal"} size={36} />
          <h1>
            {data.status === "error"
              ? "Mission data unavailable"
              : "Preparing your mission workspace"}
          </h1>
          <p>
            {data.status === "error"
              ? data.message
              : "Loading the synthetic observations and independent assessments."}
          </p>
          {data.status === "error" && (
            <button
              type="button"
              className="pv-btn"
              onClick={() => window.location.reload()}
            >
              Try again
            </button>
          )}
          <button
            type="button"
            className="pv-text-button"
            onClick={props.onOpenDebug}
          >
            Open diagnostics
          </button>
        </div>
      </div>
    );
  return <Mission data={data} {...props} />;
}

function Mission({ data, view, navigate, engineeringFixture }) {
  const { scored, observations, manifest, evaluation } = data;
  const missionLength =
    manifest?.mission_duration_days ?? FALLBACK_MISSION_LENGTH;
  const indexed = useMemo(
    () => indexMission(scored, observations ?? []),
    [scored, observations],
  );
  const [astronautId, setAstronautId] = useState(indexed.ids[0]);
  const records = useMemo(
    () => indexed.crew.get(astronautId) ?? [],
    [indexed, astronautId],
  );
  const days = useMemo(
    () => records.map((record) => record.as_of_day),
    [records],
  );
  const [day, setDay] = useState(days[0] ?? 1);
  const [playing, setPlaying] = useState(false);
  const [pauseOnAction, setPauseOnAction] = useState(true);
  const [actionStop, setActionStop] = useState(null);
  const [speed, setSpeed] = useState(1);
  const [delay, setDelay] = useState(DEFAULT_DELAY_MINUTES);
  const [autoSend, setAutoSend] = useState(true);
  const [messages, setMessages] = useState([]);
  const [consultations, setConsultations] = useState([]);
  const [now, setNow] = useState(() => Date.now());
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideStep, setGuideStep] = useState(0);
  const [controlsOpen, setControlsOpen] = useState(false);
  const [tabs, setTabs] = useState({
    dashboard: "assessments",
    ground: "snapshot",
    timeline: "chart",
    research: "summary",
  });

  const record = records.find((item) => item.as_of_day === day);
  const observation = indexed.scans.get(`${astronautId}:${day}`);
  const inTransit = messages.filter((message) => message.arrivesAt > now);
  const visibleMessages = messages.filter((message) => message.day <= day);
  const delivered = visibleMessages.filter(
    (message) => message.arrivesAt <= now,
  );
  const lastUp = delivered.filter((message) => message.dir === "up").at(-1);
  const lastDown = delivered.filter((message) => message.dir === "down").at(-1);
  const ackPending =
    lastUp && !messages.some((message) => message.ackFor === lastUp.id);
  const transitCount = inTransit.length;
  useEffect(() => {
    if (!transitCount) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(timer);
  }, [transitCount]);

  const send = useCallback(
    (dir, payload) => {
      const sentAt = Date.now();
      setMessages((list) => [
        ...list,
        {
          id: `${dir}-${sentAt}-${list.length}`,
          dir,
          sentAt,
          delay,
          arrivesAt: sentAt + delay * MS_PER_MISSION_MINUTE,
          ...payload,
        },
      ]);
      setNow(sentAt);
    },
    [delay],
  );

  const goToDay = useCallback(
    (target) => {
      setDay(target);
      if (!autoSend) return;
      const index = records.findIndex((item) => item.as_of_day === target);
      const change =
        index > 0 ? tierChange(records[index - 1], records[index]) : null;
      if (change)
        send("up", { record: records[index], day: target, reason: change });
    },
    [autoSend, records, send],
  );

  useEffect(() => {
    if (!playing || transitCount) return undefined;
    const index = days.indexOf(day);
    const timer = setTimeout(() => {
      if (index < 0 || index >= days.length - 1) return setPlaying(false);
      const next = records[index + 1];
      goToDay(next.as_of_day);
      const changes = pauseOnAction
        ? OUTCOMES.filter(
            ({ key }) =>
              ACTION_TIERS.includes(next[key].tier) &&
              records[index][key].tier !== next[key].tier,
          )
        : [];
      if (changes.length) {
        setPlaying(false);
        setActionStop({ day: next.as_of_day, changes });
      }
    }, MS_PER_DAY / speed);
    return () => clearTimeout(timer);
  }, [
    playing,
    transitCount,
    day,
    days,
    records,
    speed,
    goToDay,
    pauseOnAction,
  ]);

  function jump(target) {
    setPlaying(false);
    setActionStop(null);
    goToDay(target);
  }
  function togglePlay() {
    if (playing) return setPlaying(false);
    if (actionStop) setActionStop(null);
    else if (day === days.at(-1)) {
      setMessages([]);
      setDay(days[0]);
    }
    setPlaying(true);
  }
  function reset() {
    setPlaying(false);
    setMessages([]);
    setActionStop(null);
    setDay(days[0] ?? 1);
  }
  function selectAstronaut(id) {
    setAstronautId(id);
    setPlaying(false);
    setActionStop(null);
    setMessages([]);
    setDay(indexed.crew.get(id)?.[0]?.as_of_day ?? 1);
  }
  function skip() {
    const oldest = inTransit[0];
    if (!oldest) return;
    const timestamp = Date.now();
    setMessages((list) =>
      list.map((message) =>
        message.id === oldest.id
          ? { ...message, arrivesAt: timestamp }
          : message,
      ),
    );
    setNow(timestamp);
  }

  const onsdRows = useMemo(
    () => observationRows(indexed.scans, astronautId, missionLength),
    [indexed, astronautId, missionLength],
  );
  const range = useMemo(() => chartRange(onsdRows, day), [onsdRows, day]);
  const events = useMemo(
    () => [...reachedEvents(records, indexed.scans, day), ...consultations
      .filter(c => c.astronautId === astronautId && c.day <= day)
      .flatMap(c => c.events.map(e => ({ day: c.day, title: `Consultation · ${e.state.replaceAll("_", " ")}`,
        detail: `${c.outcome.toUpperCase()} request from mission day ${c.day}; communication timestamp ${new Date(e.at).toISOString()}. State refers to the independent communication clock.`, key: `${c.id}:${e.state}` })))].sort((a, b) => b.day - a.day),
    [records, indexed, day, consultations, astronautId],
  );
  const schemaVersion =
    observations?.[0]?.metadata?.schema_version ?? manifest?.schema_version;
  const title = TITLES[view] ?? TITLES.dashboard;
  const currentOnsd = measurementsOf(observation).find(m => m.type === "onsd");
  const quality = currentOnsd?.quality?.status;
  const latestValue =
    currentOnsd && quality !== "failed"
      ? currentOnsd.onsd_mm
      : null;
  const acknowledged = !!lastUp && !!lastDown && lastDown.ackFor === lastUp.id;

  const tab = tabs[view];
  const tabItems = {
    dashboard: [
      ["assessments", "Assessments"],
      ["measurements", "Measurements"],
    ],
    ground: [
      ["consultation", "Consultation"],
      ["snapshot", "Earth snapshot"],
      ["link", "Send update"],
      ["messages", "Messages"],
    ],
    timeline: [
      ["chart", "Charts"],
      ["changes", "Changes"],
      ["records", "Records"],
    ],
    research: [
      ["summary", "Summary"],
      ["results", "Results"],
      ["blockers", "Blockers"],
      ["capabilities", "Models"],
      ["provenance", "Run info"],
    ],
  };
  const changeTab = (value) =>
    setTabs((current) => ({ ...current, [view]: value }));
  const acknowledge = () =>
    send("down", {
      ackFor: lastUp.id,
      day: lastUp.day,
      roundTrip: lastUp.delay + delay,
    });
  const linkPanel = (
    <section className="pv-panel pv-link-panel">
      <div className="pv-panel-head">
        <h2>Deep space link</h2>
        <span className="pv-link-badge">
          <i />
          {transitCount ? "Transmitting" : "Standby"}
        </span>
      </div>
      <Link
        messages={inTransit.filter((message) => message.day <= day)}
        now={now}
        delay={delay}
        onDelay={setDelay}
        onSkip={skip}
      />
      <button
        type="button"
        className="pv-btn pv-btn--primary pv-send"
        disabled={!record}
        onClick={() => send("up", { record, day, reason: "Sent by crew" })}
      >
        <Icon name="send" size={18} />
        Send update to Earth
      </button>
      <label className="pv-check">
        <input
          type="checkbox"
          checked={autoSend}
          onChange={(event) => setAutoSend(event.target.checked)}
        />
        Auto-send on tier change
      </label>
      {lastDown && (
        <p className="pv-ack">
          <Icon name="check" size={16} />
          Day {lastDown.day} acknowledged · {lastDown.roundTrip} min round trip
        </p>
      )}
    </section>
  );
  return (
    <div className="pv" data-view={view} data-panel={tab}>
      <a
        className="pv-skip"
        href="#mission-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("mission-content")?.focus();
        }}
      >
        Skip to mission content
      </a>
      <header className="pv-topbar">
        <button
          className="pv-brand"
          type="button"
          onClick={() => navigate("home")}
        >
          <Logo />
          <span>
            ASTROSENTINEL<small>MISSION CONTROL</small>
          </span>
        </button>
        <nav aria-label="Workspace views">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={view === item.id ? "is-active" : ""}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => navigate(item.id)}
            >
              <Icon name={item.icon} size={19} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="pv-top-actions">
          <span className="pv-synthetic">
            <i />
            Synthetic mission
          </span>
          <button
            className="pv-icon-button"
            type="button"
            aria-label="Back to website"
            title="Back to website"
            onClick={() => navigate("home")}
          >
            <Icon name="external" size={20} />
          </button>
        </div>
      </header>
      <div className="pv-shell">
        {view !== "research" && (
          <CohortBrowser
            indexed={indexed}
            day={day}
            astronautId={astronautId}
            onSelect={selectAstronaut}
            onOpenResearch={() => navigate("research")}
          />
        )}
        <main id="mission-content" className="pv-workspace" tabIndex={-1}>
          {engineeringFixture && <p className="pv-notice" role="status">ENGINEERING FIXTURE · User-relayed model pending independent written approval. These cases verify functionality and are not representative experiment results. <a href="#dashboard">Return to published fixed-policy demo</a></p>}
          <header className="pv-heading">
            <div>
              <h1>
                {title[0]}
                {view !== "research" && <span> / {astronautId ?? "—"}</span>}
              </h1>
              <p>{title[1]}</p>
            </div>
            <button
              type="button"
              className="pv-btn pv-btn--quiet"
              aria-label="Quick tour"
              onClick={() => {
                setGuideStep(0);
                setGuideOpen(true);
              }}
            >
              <Icon name="info" size={18} />
              <span>Quick tour</span>
            </button>
          </header>
          {view !== "research" && (
            <section className="pv-stats" aria-label="Current mission context">
              <Stat label="Day" value={`${day} / ${missionLength}`} />
              <Stat label="Profile" value={astronautId ?? "—"} />
              <Stat
                label="ONSD"
                value={
                  Number.isFinite(latestValue)
                    ? `${latestValue.toFixed(2)} mm`
                    : "Unavailable"
                }
              />
              <Stat
                label="Earth"
                value={lastUp ? `Day ${lastUp.day}` : "No update"}
              />
            </section>
          )}
          {view !== "research" && (
            <section className="pv-playback" aria-label="Mission playback">
              <button
                type="button"
                className="pv-play"
                disabled={!days.length}
                onClick={togglePlay}
                aria-label={
                  playing
                    ? "Pause playback"
                    : actionStop
                      ? "Continue mission"
                      : day === days.at(-1)
                        ? "Replay mission"
                        : "Play mission"
                }
              >
                <Icon name={playing ? "pause" : "play"} size={20} />
              </button>
              <div className="pv-day-readout">
                <strong>Day {day}</strong>
                <small>
                  {playing
                    ? transitCount
                      ? "Waiting for link"
                      : "Playing"
                    : "Playback"}
                </small>
              </div>
              <input
                className="pv-scrub"
                type="range"
                min={days[0] ?? 1}
                max={days.at(-1) ?? missionLength}
                value={day}
                disabled={!days.length}
                aria-label="Mission day"
                onChange={(event) => {
                  const value = Number(event.target.value);
                  const nearest = days.reduce(
                    (best, next) =>
                      Math.abs(next - value) < Math.abs(best - value)
                        ? next
                        : best,
                    days[0],
                  );
                  if (nearest !== undefined) jump(nearest);
                }}
              />
              <div
                className="pv-speed"
                role="group"
                aria-label="Playback speed"
              >
                {SPEEDS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={value === speed}
                    className={value === speed ? "is-on" : ""}
                    onClick={() => setSpeed(value)}
                  >
                    {value}×
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="pv-icon-button pv-reset"
                aria-label="Restart mission playback"
                onClick={reset}
              >
                <Icon name="reset" size={19} />
              </button>
              <button
                type="button"
                className="pv-icon-button"
                aria-label="Playback settings"
                title="Playback settings"
                onClick={() => setControlsOpen(true)}
              >
                <Icon name="menu" size={19} />
              </button>
            </section>
          )}
          {actionStop && view !== "research" && (
            <div className="pv-action" role="alert">
              <Icon name="info" size={20} />
              <span>
                <strong>Recorded action · Day {actionStop.day}</strong>
                <span>
                  {actionStop.changes.map(({ key, name }) => `${name}: ${record?.[key]?.recommended_action?.text ?? record?.[key]?.explanation ?? "Evidence unavailable"}`).join(" ")}
                </span>
              </span>
              <button
                type="button"
                className="pv-btn"
                onClick={() => {
                  setActionStop(null);
                  setPlaying(true);
                }}
              >
                Continue
                <Icon name="arrow" size={17} />
              </button>
            </div>
          )}
          {(!indexed.ids.length ||
            (schemaVersion && schemaVersion !== EXPECTED_SCHEMA_VERSION)) && (
            <p className="pv-notice">
              {!indexed.ids.length
                ? "No scored profiles are available."
                : `Data schema ${schemaVersion}; expected ${EXPECTED_SCHEMA_VERSION}. Check diagnostics.`}
            </p>
          )}
          <div className="pv-content-grid">
            <div className="pv-main-column">
              <Tabs
                label="Workspace sections"
                items={tabItems[view]}
                value={tab}
                onChange={changeTab}
              />
              <div
                className="pv-panel-slot"
                role="tabpanel"
                aria-label={tabItems[view].find(([id]) => id === tab)?.[1]}
              >
                {view === "dashboard" &&
                  (tab === "assessments" ? (
                    <OutcomeGroup record={record} />
                  ) : (
                    <TodayData observation={observation} rows={onsdRows} day={day} />
                  ))}
                {view === "timeline" &&
                  (tab === "chart" ? (
                    <TrendsPanel
                      astronautId={astronautId}
                      records={records}
                      onsdRows={onsdRows}
                      onsdRange={range}
                      missionLength={missionLength}
                      day={day}
                      onJump={jump}
                    />
                  ) : tab === "changes" ? (
                    <EventPanel events={events} day={day} onJump={(target) => { jump(target); setTabs(current => ({ ...current, timeline: "records" })); }} />
                  ) : (
                    <ObservationPanel
                      rows={onsdRows}
                      day={day}
                      astronautId={astronautId}
                    />
                  ))}
                {view === "ground" &&
                  (tab === "consultation" ? (
                    <ConsultationPanel record={record} observation={observation}
                      evidenceObservations={Object.fromEntries(OUTCOMES.map(({ key }) => [key, indexed.scans.get(`${astronautId}:${record?.[key]?.evidence_day}`)]))}
                      cases={consultations} onCases={setConsultations} delay={delay} onDelay={setDelay} />
                  ) : tab === "snapshot" ? (
                    <GroundSnapshot
                      lastUp={lastUp}
                      day={day}
                      ackPending={ackPending}
                      acknowledged={acknowledged}
                      onAcknowledge={acknowledge}
                      onSend={() => changeTab("link")}
                    />
                  ) : tab === "link" ? (
                    linkPanel
                  ) : (
                    <TransmissionPanel messages={visibleMessages} now={now} />
                  ))}
                {view === "research" && (
                  <ResearchPanel
                    manifest={manifest}
                    evaluation={evaluation}
                    tab={tab}
                  />
                )}
              </div>
            </div>
            {view !== "research" && !(view === "ground" && tab === "link") && (
              <aside
                className="pv-right-column"
                aria-label="Communication controls"
              >
                {linkPanel}
              </aside>
            )}
          </div>
          <footer className="pv-foot">
            <span>
              <i />
              Synthetic research · Not clinically validated
            </span>
            <button type="button" onClick={() => navigate("research")}>
              Model limitations
              <Icon name="external" size={14} />
            </button>
          </footer>
        </main>
      </div>
      {guideOpen && (
        <Dialog
          title="Workspace quick tour"
          onClose={() => setGuideOpen(false)}
        >
          <Tour
            step={guideStep}
            onNext={() => setGuideStep((step) => step + 1)}
            onClose={() => setGuideOpen(false)}
          />
        </Dialog>
      )}
      {controlsOpen && (
        <Dialog
          title="Playback settings"
          onClose={() => setControlsOpen(false)}
        >
          <div className="pv-settings">
            <label>
              <span>Playback speed</span>
              <select
                aria-label="Playback speed setting"
                value={speed}
                onChange={(event) => setSpeed(Number(event.target.value))}
              >
                {SPEEDS.map((value) => (
                  <option key={value} value={value}>
                    {value}×
                  </option>
                ))}
              </select>
            </label>
            <label className="pv-check">
              <input
                type="checkbox"
                checked={pauseOnAction}
                onChange={(event) => setPauseOnAction(event.target.checked)}
              />
              Pause when a tier changes to an action tier
            </label>
            <p>
              Changing the day pauses playback. The Earth link uses its own
              simulated delay, independent of playback speed.
            </p>
          </div>
        </Dialog>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="pv-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function GroundSnapshot({
  lastUp,
  day,
  ackPending,
  acknowledged,
  onAcknowledge,
  onSend,
}) {
  return (
    <section className="pv-panel pv-ground">
      <div className="pv-panel-head">
        <h2>Earth’s received snapshot</h2>
        <span className="pv-subtle">
          {lastUp ? `Day ${lastUp.day}` : "Not received"}
        </span>
      </div>
      {lastUp ? (
        <>
          <div className="pv-ground-time">
            <span>
              {lastUp.day === day
                ? "Matches onboard day"
                : `${day - lastUp.day} mission day(s) behind`}
            </span>
            <span>
              {acknowledged
                ? "Acknowledged"
                : ackPending
                  ? "Awaiting acknowledgement"
                  : "Reply in transit"}
            </span>
          </div>
          <OutcomeGroup record={lastUp.record} />
          {ackPending && (
            <button
              className="pv-btn pv-btn--primary"
              type="button"
              onClick={onAcknowledge}
            >
              <Icon name="check" size={18} />
              Acknowledge snapshot
            </button>
          )}
        </>
      ) : (
        <div className="pv-empty-state">
          <Icon name="signal" size={36} />
          <h3>No snapshot received</h3>
          <p>
            Earth sees a snapshot only after it arrives. Send the current
            onboard day to begin.
          </p>
          <button
            className="pv-btn pv-btn--primary"
            type="button"
            onClick={onSend}
          >
            Send an update
            <Icon name="arrow" size={18} />
          </button>
        </div>
      )}
    </section>
  );
}

function Tour({ step, onNext, onClose }) {
  const steps = [
    [
      "Choose a profile",
      "Search or filter the synthetic cohort. Use the page arrows to browse without scrolling.",
    ],
    [
      "Explore one task at a time",
      "Use the section tabs to switch between assessments, measurements, charts, and records. View evidence opens the full recorded explanation.",
    ],
    [
      "Share the onboard perspective",
      "Open Earth link, then Send update. A snapshot appears on Earth only after its simulated delay.",
    ],
  ];
  const current = steps[Math.min(step, 2)];
  return (
    <>
      <div className="pv-dialog-body">
        <span className="pv-eyebrow">STEP {Math.min(step + 1, 3)} OF 3</span>
        <h3>{current[0]}</h3>
        <p>{current[1]}</p>
      </div>
      <div className="pv-dialog-actions">
        <button
          className="pv-btn pv-btn--primary"
          type="button"
          onClick={step >= 2 ? onClose : onNext}
        >
          {step >= 2 ? "Start exploring" : "Next"}
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </>
  );
}

function TodayData({ observation, rows = [], day }) {
  const scans = measurementsOf(observation);
  const scan = scans.find(m => m.type === "onsd");
  const jugularScan = scans.find(m => m.type === "jugular");
  const quality = scan?.quality?.status;
  const lastOnsd = rows.findLast(r => r.day <= day && r.onsd != null);
  const lastJugular = rows.findLast(r => r.day <= day && r.jugular != null);
  const onsd =
    scan?.type === "onsd" && quality !== "failed" ? scan.onsd_mm : null;
  const jugular =
    jugularScan && jugularScan.quality?.status !== "failed"
      ? [
          jugularScan.jugular_flow_class,
          jugularScan.jugular_area_mm2 !== null && jugularScan.jugular_area_mm2 !== undefined
            ? `${jugularScan.jugular_area_mm2.toFixed(1)} mm²`
            : null,
          jugularScan.jugular_baseline_mm2 != null && jugularScan.jugular_area_mm2 != null
            ? `Baseline ${jugularScan.jugular_baseline_mm2.toFixed(1)} mm²; change ${(jugularScan.jugular_area_mm2 - jugularScan.jugular_baseline_mm2).toFixed(1)} mm²; quality ${jugularScan.quality?.status ?? "unknown"}`
            : null,
        ]
          .filter(Boolean)
          .join(" · ")
      : "";
  const signals = Object.entries(observation?.weak_signals ?? {}).filter(
    ([, value]) => value !== null && value !== undefined,
  );
  return (
    <section className="pv-panel pv-measurements">
      <div className="pv-panel-head">
        <h2>Today’s measurements</h2>
        <span className="pv-subtle">Recorded observations</span>
      </div>
      <dl>
        <div><dt>Latest recorded ONSD</dt><dd>{lastOnsd ? `${lastOnsd.onsd.toFixed(2)} mm · Day ${lastOnsd.day} · ${QUALITY_TEXT[lastOnsd.quality] ?? "Quality unknown"}` : "Unavailable"}</dd></div>
        <div><dt>Latest recorded jugular area and flow</dt><dd>{lastJugular ? `${lastJugular.jugular.toFixed(1)} mm² · ${lastJugular.flow ?? "Flow unavailable"} · Day ${lastJugular.day} · ${QUALITY_TEXT[lastJugular.jugularQuality] ?? "Quality unknown"}; baseline ${lastJugular.jugularBaseline?.toFixed(1) ?? "unavailable"} mm²` : "Unavailable"}</dd></div>
        <div><dt>Acquisition policy</dt><dd>{observation?.metadata?.acquisition_policy ?? "Not recorded"} · {observation?.metadata?.scheduling_reason ?? "No scheduling reason"}</dd></div>
        <div><dt>Personal ONSD baseline</dt><dd>{Number.isFinite(scan?.onsd_baseline_mm ?? lastOnsd?.baseline) ? `${(scan?.onsd_baseline_mm ?? lastOnsd.baseline).toFixed(2)} mm; latest recorded change ${lastOnsd?.baseline != null ? `${(lastOnsd.onsd - lastOnsd.baseline).toFixed(2)} mm` : "unavailable"}` : "Unavailable; no baseline inferred from the first scan"}</dd></div>
        <div><dt>Last good ONSD observation</dt><dd>{rows.findLast(r => r.day <= day && r.quality === "ok" && r.onsd !== null)?.day ?? "Unavailable"}</dd></div>
        <div>
          <dt>
            <Icon name="eye" size={16} />
            ONSD scan
          </dt>
          <dd>
            {Number.isFinite(onsd) ? (
              <>
                <strong>
                  {onsd.toFixed(2)} <small>mm</small>
                </strong>
                <span className={`pv-quality pv-quality-${quality}`}>
                  {QUALITY_TEXT[quality] ?? "Quality not recorded"}
                </span>
              </>
            ) : (
              <span>
                {scan?.type === "onsd" && quality === "failed"
                  ? "Failed quality check · value unavailable"
                  : "Unavailable"}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>
            <Icon name="pulse" size={16} />
            Jugular scan
          </dt>
          <dd>
            {jugular ||
              (jugularScan?.quality?.status === "failed"
                ? "Failed quality check · value unavailable"
                : "Unavailable in this record")}
          </dd>
        </div>
        <div>
          <dt>Last good jugular observation</dt><dd>{rows.findLast(r => r.day <= day && r.jugularQuality === "ok" && r.jugular !== null)?.day ?? "Unavailable"}</dd>
        </div>
        <div>
          <dt>
            <Icon name="signal" size={16} />
            Daily weak signals
          </dt>
          <dd>
            {signals.length
              ? signals
                  .map(
                    ([key, value]) => `${key.replaceAll("_", " ")}: ${value}`,
                  )
                  .join(" · ")
              : observation
                ? "No weak signals in this record"
                : "Observation unavailable"}
          </dd>
        </div>
      </dl>
      <p className="pv-subtle">Synthetic recorded measurements; acquisition quality and baseline change do not establish a diagnosis. Monitoring estimates and model limitations are shown in Assessments. Unscheduled days contain no acquisition.</p>
    </section>
  );
}

// The dot's travel time is the message's own delay (arrivesAt - sentAt), so it
// reaches Earth exactly when the countdown hits zero. A CSS animation gives
// smooth motion; the animation clock is anchored once, on mount, by offsetting
// it by the time already elapsed (e.g. when the panel is opened mid-transit).
// --progress is the fallback position when motion is reduced.
function TransmissionDot({ message, now }) {
  const duration = Math.max(1, message.arrivesAt - message.sentAt);
  const [elapsedAtMount] = useState(() =>
    Math.min(duration, Math.max(0, Date.now() - message.sentAt)),
  );
  const progress = Math.min(1, Math.max(0, (now - message.sentAt) / duration));
  return (
    <span
      className={`pv-transmission-dot${message.dir === "down" ? " is-returning" : ""}`}
      style={{
        "--progress": progress,
        "--duration": `${duration}ms`,
        "--start-offset": `${-elapsedAtMount}ms`,
      }}
    />
  );
}

function Link({ messages, now, delay, onDelay, onSkip }) {
  return (
    <>
      <div className="pv-link-visual">
        <img
          src="/images/mission-link.svg"
          alt="Mars to Earth communication path"
        />
        {messages.length > 0 && (
          <TransmissionDot
            key={messages[0].id}
            message={messages[0]}
            now={now}
          />
        )}
      </div>
      <div className="pv-link-labels">
        <span>ONBOARD / MARS</span>
        <span>GROUND / EARTH</span>
      </div>
      <div className="pv-link-status" role="status">
        {messages.length ? (
          <>
            <strong>
              {messages[0].dir === "up" ? "Snapshot to Earth" : "Reply to crew"}
            </strong>
            <div>
              <span className="pv-countdown">
                {countdown(messages[0].arrivesAt - now)}
              </span>
              <button type="button" className="pv-text-button" onClick={onSkip}>
                Skip delay <Icon name="arrow" size={13} />
              </button>
            </div>
            {messages.length > 1 && (
              <small>{messages.length - 1} additional transmission(s)</small>
            )}
          </>
        ) : (
          <>
            <strong>Ready when you are.</strong>
            <span>Send a snapshot of the current mission day.</span>
          </>
        )}
      </div>
      <label className="pv-delay">
        <span>
          One-way delay <strong>{delay} min</strong>
        </span>
        <input
          type="range"
          min={0}
          max={MAX_DELAY_MINUTES}
          value={delay}
          aria-label="One-way communication delay"
          onChange={(event) => onDelay(Number(event.target.value))}
        />
        <small>Simulated · 1 second represents 1 minute</small>
      </label>
    </>
  );
}
