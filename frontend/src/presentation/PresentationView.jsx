import '@fontsource/barlow/400.css'
import '@fontsource/barlow/500.css'
import '@fontsource/barlow-semi-condensed/500.css'
import '@fontsource/barlow-semi-condensed/600.css'
import './presentation.css'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ACTION_TIERS,
  DEFAULT_DELAY_MINUTES,
  FALLBACK_MISSION_LENGTH,
  FALLBACK_SYNTHETIC_LABEL,
  MAX_DELAY_MINUTES,
  MS_PER_DAY,
  MS_PER_MISSION_MINUTE,
  OUTCOMES,
  QUALITY_TEXT,
  SPEEDS,
  TIER_TEXT,
} from './constants.js'
import { OutcomeTile } from './OutcomeTile.jsx'
import { TrendsPanel } from './TrendsPanel.jsx'
import { useMissionData } from './useMissionData.js'

// "0:09" from milliseconds, rounded up so it only reads 0:00 on arrival.
function countdown(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

// Describes a tier change between two records, SANS and Venous separately.
function tierChange(previous, record) {
  if (!previous || !record) return null
  const parts = OUTCOMES.filter((o) => previous[o.key].tier !== record[o.key].tier).map(
    (o) => `${o.name} ${TIER_TEXT[previous[o.key].tier]?.label ?? previous[o.key].tier} to ${TIER_TEXT[record[o.key].tier]?.label ?? record[o.key].tier}`,
  )
  return parts.length ? parts.join(', ') : null
}

// The outcomes whose tier changed to one that needs action since the previous
// recorded day. It reads the backend's tier values and nothing else.
function actionChanges(previous, record) {
  return OUTCOMES.filter(
    (o) => ACTION_TIERS.includes(record[o.key].tier) && previous[o.key].tier !== record[o.key].tier,
  ).map((o) => ({ name: o.name, tier: record[o.key].tier }))
}

let nextMessageId = 1

export default function PresentationView({ onOpenDebug }) {
  const data = useMissionData()

  if (data.status === 'loading') {
    return <div className="pv pv-center">Loading mission data…</div>
  }
  if (data.status === 'error') {
    return (
      <div className="pv pv-center">
        <div>
          <p>The mission data could not be loaded: {data.message}</p>
          <p className="pv-muted">Check that the pipeline run files are in frontend/public/data, then reload.</p>
          <button type="button" className="pv-btn" onClick={onOpenDebug}>Open debug view</button>
        </div>
      </div>
    )
  }
  return <Mission data={data} onOpenDebug={onOpenDebug} />
}

function Mission({ data, onOpenDebug }) {
  const { scored, observations, manifest, evaluation } = data
  const missionLength = manifest?.mission_duration_days ?? FALLBACK_MISSION_LENGTH
  const syntheticLabel = observations?.[0]?.metadata?.synthetic_label || FALLBACK_SYNTHETIC_LABEL

  // Every astronaut's records, sorted by day.
  const crew = useMemo(() => {
    const map = new Map()
    for (const record of scored) {
      if (!map.has(record.astronaut_id)) map.set(record.astronaut_id, [])
      map.get(record.astronaut_id).push(record)
    }
    for (const list of map.values()) list.sort((a, b) => a.as_of_day - b.as_of_day)
    return map
  }, [scored])
  const crewIds = useMemo(() => [...crew.keys()].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })), [crew])

  const [astronautId, setAstronautId] = useState(crewIds[0])
  const records = useMemo(() => crew.get(astronautId) ?? [], [crew, astronautId])
  const days = useMemo(() => records.map((r) => r.as_of_day), [records])
  const [day, setDay] = useState(days[0] ?? 1)
  const [playing, setPlaying] = useState(false)
  const [pauseOnAction, setPauseOnAction] = useState(true)
  const [actionStop, setActionStop] = useState(null) // the banner's day and changes, or null
  const [speed, setSpeed] = useState(1)
  const [delay, setDelay] = useState(DEFAULT_DELAY_MINUTES)
  const [autoSend, setAutoSend] = useState(true)
  const [messages, setMessages] = useState([])
  const [now, setNow] = useState(() => Date.now())

  const record = records.find((r) => r.as_of_day === day)
  const observation = observations?.find((o) => o.astronaut_id === astronautId && o.day === day)

  const inTransit = messages.filter((m) => m.arrivesAt > now)
  const delivered = messages.filter((m) => m.arrivesAt <= now)
  const lastUp = delivered.filter((m) => m.dir === 'up').at(-1)
  const lastDown = delivered.filter((m) => m.dir === 'down').at(-1)
  const ackPending = lastUp && !messages.some((m) => m.dir === 'down' && m.ackFor === lastUp.id)

  // Keep "now" moving while something is in transit, so countdowns update.
  const transitCount = inTransit.length
  useEffect(() => {
    if (transitCount === 0) return undefined
    const timer = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(timer)
  }, [transitCount])

  const send = useCallback(
    (dir, payload) => {
      const sentAt = Date.now()
      const message = { id: nextMessageId++, dir, sentAt, delay, arrivesAt: sentAt + delay * MS_PER_MISSION_MINUTE, ...payload }
      setMessages((list) => [...list, message])
      setNow(sentAt)
    },
    [delay],
  )

  // Move to a day. With auto-send on, a tier change from the previous recorded
  // day is sent to Earth.
  const goToDay = useCallback(
    (target) => {
      setDay(target)
      if (!autoSend) return
      const index = records.findIndex((r) => r.as_of_day === target)
      const change = index > 0 ? tierChange(records[index - 1], records[index]) : null
      if (change) send('up', { record: records[index], day: target, reason: `Tier change: ${change}` })
    },
    [autoSend, records, send],
  )

  // Playback: one day every 2 s at 1x. It holds while a message is in transit,
  // and carries on when the message arrives. It stops completely when a tier
  // changes to one that needs action. Only this timer checks for that, so moving
  // the slider or clicking the strip never stops anything.
  const holding = transitCount > 0
  useEffect(() => {
    if (!playing || holding) return undefined
    const index = days.indexOf(day)
    const timer = setTimeout(() => {
      if (index === -1 || index >= days.length - 1) {
        setPlaying(false)
        return
      }
      const nextDay = days[index + 1]
      goToDay(nextDay) // this sends the update first, if auto-send is on
      const changes = pauseOnAction ? actionChanges(records[index], records[index + 1]) : []
      if (changes.length > 0) {
        setPlaying(false)
        setActionStop({ day: nextDay, changes })
      }
    }, MS_PER_DAY / speed)
    return () => clearTimeout(timer)
  }, [playing, holding, day, days, records, speed, goToDay, pauseOnAction])

  const atEnd = days.indexOf(day) === days.length - 1

  // Dismisses the banner and carries on from this day. If a message is still in
  // transit, the hold above applies until it arrives.
  function continueMission() {
    setActionStop(null)
    setPlaying(true)
  }

  function togglePlay() {
    // This comes first, so continuing from the last day doesn't restart the mission.
    if (actionStop) return continueMission()
    if (playing) return setPlaying(false)
    if (atEnd) {
      setMessages([])
      setDay(days[0])
    }
    setPlaying(true)
  }

  function jump(target) {
    setPlaying(false)
    setActionStop(null) // the banner describes the day the user is moving away from
    goToDay(target)
  }

  function scrub(value) {
    // Snap the slider to the nearest day that has a record.
    const nearest = days.reduce((best, d) => (Math.abs(d - value) < Math.abs(best - value) ? d : best), days[0])
    jump(nearest)
  }

  function selectAstronaut(id) {
    setAstronautId(id)
    setPlaying(false)
    setActionStop(null)
    setMessages([])
    setDay(crew.get(id)?.[0]?.as_of_day ?? 1)
  }

  function skip() {
    const oldest = inTransit[0]
    if (!oldest) return
    const t = Date.now()
    setMessages((list) => list.map((m) => (m.id === oldest.id ? { ...m, arrivesAt: t } : m)))
    setNow(t)
  }

  // ONSD values for the chart, one row per mission day.
  const onsdRows = useMemo(() => {
    const byDay = new Map((observations ?? []).filter((o) => o.astronaut_id === astronautId).map((o) => [o.day, o]))
    return Array.from({ length: missionLength }, (_, i) => {
      const scan = byDay.get(i + 1)?.scan
      return { day: i + 1, onsd: scan?.onsd_mm ?? null, quality: scan?.quality?.status ?? null }
    })
  }, [observations, astronautId, missionLength])

  // The chart's y-axis range, worked out once from every astronaut's values, so it
  // doesn't jump as new points appear. This only sizes the axis: the data's own min
  // and max, rounded outwards, with room below for the failed-scan crosses.
  const onsdRange = useMemo(() => {
    const values = (observations ?? []).map((o) => o.scan?.onsd_mm).filter((v) => v !== null && v !== undefined)
    if (values.length === 0) return null
    const low = Math.floor(Math.min(...values) * 4) / 4 - 0.25
    const high = Math.ceil(Math.max(...values) * 4) / 4
    // Ticks every 0.5 mm, so each label is exactly where its line is drawn.
    const firstTick = Math.ceil(low * 2) / 2
    const ticks = Array.from({ length: Math.floor((high - firstTick) * 2) + 1 }, (_, i) => firstTick + i * 0.5)
    return { low, high, ticks }
  }, [observations])

  // Roster: each astronaut's tiers on the current day (or the latest day before it).
  function rosterRecord(id) {
    const list = crew.get(id) ?? []
    return [...list].reverse().find((r) => r.as_of_day <= day) ?? list[0]
  }

  return (
    <div className="pv">
      <header className="pv-top">
        <div className="pv-brand">
          <h1>AstroSentinel</h1>
          <p>Onboard fluid-shift monitoring for a Mars transit crew</p>
        </div>
        <p className="pv-synthetic" role="note">{syntheticLabel}</p>
        <button type="button" className="pv-btn pv-btn--ghost" onClick={onOpenDebug}>Debug view</button>
      </header>

      <section className="pv-playback" aria-label="Mission playback">
        <button type="button" className="pv-play" onClick={togglePlay} aria-label={actionStop ? 'Continue mission' : playing ? 'Pause playback' : atEnd ? 'Replay mission' : 'Play mission'}>
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <div className="pv-day-readout">
          <span className="pv-day-num">Day {day}</span>
          <span className="pv-muted">of {missionLength}</span>
        </div>
        <input
          className="pv-scrub"
          type="range"
          min={days[0] ?? 1}
          max={days.at(-1) ?? missionLength}
          value={day}
          onChange={(e) => scrub(Number(e.target.value))}
          aria-label="Mission day"
        />
        <div className="pv-speed" role="group" aria-label="Playback speed">
          {SPEEDS.map((s) => (
            <button key={s} type="button" className={s === speed ? 'is-on' : ''} aria-pressed={s === speed} onClick={() => setSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
        <label className="pv-check">
          <input type="checkbox" checked={pauseOnAction} onChange={(e) => setPauseOnAction(e.target.checked)} />
          Pause when action is needed
        </label>
        {holding && playing && <span className="pv-hold">Holding for transmission</span>}
      </section>

      <nav className="pv-roster" aria-label="Crew">
        {crewIds.map((id) => {
          const r = rosterRecord(id)
          return (
            <button key={id} type="button" className={`pv-chip${id === astronautId ? ' is-on' : ''}`} onClick={() => selectAstronaut(id)} aria-pressed={id === astronautId}>
              <span className="pv-chip-id">{id}</span>
              {OUTCOMES.map((o) => (
                <span key={o.key} className={`pv-chip-dot pv-tier-${r?.[o.key]?.tier ?? 'unresolved'}`} title={`${o.name}: ${TIER_TEXT[r?.[o.key]?.tier]?.label ?? 'no record'}`} />
              ))}
            </button>
          )
        })}
        <span className="pv-roster-key pv-muted">Left dot SANS, right dot Venous</span>
      </nav>

      <main className="pv-stage">
        {actionStop && <ActionBanner stop={actionStop} onContinue={continueMission} />}

        <section className="pv-panel pv-crew" aria-labelledby="pv-crew-title">
          <header className="pv-panel-head">
            <h2 id="pv-crew-title">Crew, onboard</h2>
            <span className="pv-muted">{astronautId}, day {day}</span>
          </header>
          <div className="pv-tiles">
            {OUTCOMES.map((meta) => (
              <OutcomeTile key={meta.key} meta={meta} outcome={record?.[meta.key]} />
            ))}
          </div>
          <TodayData observation={observation} />
          <div className="pv-crew-actions">
            <button type="button" className="pv-btn" disabled={!record} onClick={() => send('up', { record, day, reason: 'Sent by crew' })}>
              Send update to Earth
            </button>
            <label className="pv-check">
              <input type="checkbox" checked={autoSend} onChange={(e) => setAutoSend(e.target.checked)} />
              Send automatically when a tier changes
            </label>
          </div>
          {lastDown && (
            <p className="pv-ack">
              Earth acknowledged the day {lastDown.day} update. Round trip {lastDown.roundTrip} min, simulated.
            </p>
          )}
        </section>

        <Link messages={inTransit} now={now} delay={delay} onDelay={setDelay} onSkip={skip} />

        <section className="pv-panel pv-ground" aria-labelledby="pv-ground-title">
          <header className="pv-panel-head">
            <h2 id="pv-ground-title">Ground, Earth</h2>
            <span className="pv-muted">{lastUp ? `Last received: day ${lastUp.day}` : 'Nothing received yet'}</span>
          </header>
          {lastUp ? (
            <>
              <div className="pv-tiles">
                {OUTCOMES.map((meta) => (
                  <OutcomeTile key={meta.key} meta={meta} outcome={lastUp.record[meta.key]} compact />
                ))}
              </div>
              <p className="pv-behind">
                {lastUp.day === day ? 'Earth is up to date with the crew.' : `Earth is seeing day ${lastUp.day}. The crew is on day ${day}.`}
              </p>
              <p className="pv-muted pv-small">{lastUp.reason}</p>
              {ackPending && (
                <button type="button" className="pv-btn pv-btn--earth" onClick={() => send('down', { ackFor: lastUp.id, day: lastUp.day, roundTrip: lastUp.delay + delay })}>
                  Acknowledge
                </button>
              )}
            </>
          ) : (
            <p className="pv-empty">Earth has no update yet. Send one from the crew panel, or press play.</p>
          )}
        </section>
      </main>

      <TrendsPanel astronautId={astronautId} records={records} onsdRows={onsdRows} onsdRange={onsdRange} missionLength={missionLength} day={day} onJump={jump} />

      <Footer manifest={manifest} evaluation={evaluation} />
    </div>
  )
}

// Shown when playback stops because a tier changed to one that needs action. With
// two outcomes on one day, the banner takes the colour of the later tier in
// ACTION_TIERS, and each outcome's name keeps its own tier's colour.
function ActionBanner({ stop, onContinue }) {
  const bannerTier = ACTION_TIERS.findLast((tier) => stop.changes.some((change) => change.tier === tier))
  return (
    <div className={`pv-action pv-tier-${bannerTier}`} role="alert">
      <p>
        Action needed, Day {stop.day}:{' '}
        {stop.changes.map((change, index) => (
          <span key={change.name}>
            {index > 0 && '; '}
            <strong className={`pv-tier-${change.tier}`}>{change.name} {TIER_TEXT[change.tier].label}</strong>
            {' – '}
            {TIER_TEXT[change.tier].action}
          </span>
        ))}
      </p>
      <button type="button" className="pv-btn pv-action-continue" onClick={onContinue}>
        Continue mission
      </button>
    </div>
  )
}

// What was measured today, from the observation file only.
function TodayData({ observation }) {
  if (!observation) return <p className="pv-today pv-muted">No observation record for this day.</p>
  const scan = observation.scan
  const status = scan?.quality?.status
  const onsd = scan?.type === 'onsd'
    ? `${scan.onsd_mm !== null && scan.onsd_mm !== undefined ? `${scan.onsd_mm.toFixed(2)} mm, ` : ''}${QUALITY_TEXT[status]?.toLowerCase() ?? status ?? 'quality not recorded'}`
    : 'none today'
  const jugular = scan?.jugular_area_mm2 !== null && scan?.jugular_area_mm2 !== undefined ? `${scan.jugular_area_mm2} mm²` : 'not available'
  return (
    <dl className="pv-today">
      <div className={status === 'failed' ? 'is-warn' : ''}><dt>ONSD scan</dt><dd>{onsd}</dd></div>
      <div><dt>Jugular scan</dt><dd>{jugular}</dd></div>
      <div><dt>Daily signals</dt><dd>{observation.weak_signals ? 'available, hypothesis only' : 'not available'}</dd></div>
    </dl>
  )
}

// The signal path between Mars and Earth, with messages travelling along it.
function Link({ messages, now, delay, onDelay, onSkip }) {
  return (
    <section className="pv-link" aria-label="Communication delay">
      <div className="pv-link-track" aria-hidden="true">
        <span className="pv-planet pv-planet--mars">Mars</span>
        <span className="pv-planet pv-planet--earth">Earth</span>
        {messages.map((m) => {
          const progress = Math.min(1, Math.max(0, (now - m.sentAt) / (m.arrivesAt - m.sentAt || 1)))
          const along = m.dir === 'up' ? progress : 1 - progress
          return <span key={m.id} className={`pv-packet pv-packet--${m.dir}`} style={{ '--along': along }} />
        })}
      </div>
      <div className="pv-link-status" aria-live="polite">
        {messages.length > 0 ? (
          <>
            <strong>{messages[0].dir === 'up' ? 'Update to Earth' : 'Reply to crew'}</strong>
            <span>arrives in {countdown(messages[0].arrivesAt - now)}</span>
            {messages.length > 1 && <span className="pv-muted">+{messages.length - 1} queued</span>}
            <button type="button" className="pv-link-skip" onClick={onSkip}>Skip</button>
          </>
        ) : (
          <span className="pv-muted">No message in transit</span>
        )}
      </div>
      <label className="pv-delay">
        <span>One-way delay <strong>{delay} min</strong></span>
        <input type="range" min={0} max={MAX_DELAY_MINUTES} value={delay} onChange={(e) => onDelay(Number(e.target.value))} />
        <span className="pv-muted pv-small">Demo time: 1 second stands for 1 minute</span>
      </label>
    </section>
  )
}

function readable(id) {
  const text = id.replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function Footer({ manifest, evaluation }) {
  const blockers = evaluation?.blockers ?? []
  return (
    <footer className="pv-foot">
      <div className="pv-result" tabIndex={blockers.length ? 0 : undefined}>
        <strong>Adaptive vs fixed scanning</strong>
        <span>{evaluation ? (blockers.length ? 'Result pending approval of the remaining assumptions' : 'Result available') : 'No evaluation file loaded'}</span>
        {blockers.length > 0 && (
          <div className="pv-pop pv-pop--up" role="tooltip">
            <p>The backend will not produce this comparison until these are resolved:</p>
            <ul>{blockers.map((b) => <li key={b.capability}>{readable(b.capability)}</li>)}</ul>
          </div>
        )}
      </div>
      {manifest && (
        <p className="pv-muted pv-small">
          Run {manifest.run_id}: {manifest.crew_size} simulated astronauts over {manifest.mission_duration_days} days. Generation {String(manifest.generation_status).replaceAll('_', ' ')}.
        </p>
      )}
    </footer>
  )
}

function PlayIcon() {
  return <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" /></svg>
}
function PauseIcon() {
  return <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" /></svg>
}
