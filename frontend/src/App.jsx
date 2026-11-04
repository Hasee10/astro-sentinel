// useState lets a component remember a value between screen updates.
// useEffect lets a component run code after it appears on screen.
// useEffectEvent makes a function that a useEffect can call, and that always
// sees the latest values without making the useEffect start over.
import { useEffect, useEffectEvent, useState } from 'react'
// Recharts draws the ONSD chart from these building blocks.
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

// The data files the user can choose from. Files in the "public" folder are
// served from the root of the website, so public/data/example.jsonl is
// available at /data/example.jsonl.
//   label       = the text shown in the dropdown
//   url         = where to load the file from
//   manifestUrl = where to read this file's mission length from
//   summaryUrl  = where to read this file's run summary from, if it has one
//   observationsUrl = where to read this file's scans from, if it has any
//   isFixture   = true for hand-made test data, which needs a warning on screen
//
// The first file in this list is the one selected when the page opens.
//
// ground_truth.jsonl must never be listed here or copied into public/data. It
// holds the hidden answers used to evaluate the backend, and the handoff docs
// say the frontend must never read or display it.
const DATA_FILES = [
  {
    label: 'Pipeline run (8 astronauts)',
    url: '/data/crew_scored.jsonl',
    manifestUrl: '/data/simulation_manifest.json',
    summaryUrl: '/data/scoring_summary.json',
    observationsUrl: '/data/crew_observations.jsonl',
    isFixture: false,
  },
  {
    label: 'Pipeline output (blocked)',
    url: '/data/example_scored_blocked.jsonl',
    manifestUrl: '/data/example_simulation_manifest.json',
    isFixture: false,
  },
  {
    label: 'UI test fixture',
    url: '/data/example_engineering_fixture_scored.jsonl',
    manifestUrl: '/data/example_simulation_manifest.json',
    isFixture: true,
  },
]

// Mission playback: at 1× speed, each day stays on screen for 2000 milliseconds
// (2 seconds). At 2× it stays half as long, and at 4× a quarter as long.
const MS_PER_DAY_AT_1X = 2000
const PLAYBACK_SPEEDS = [1, 2, 4]

// The mission length comes from the chosen file's manifest. If we can't get it
// from there, we use this fallback and show a note saying so.
const FALLBACK_MISSION_LENGTH = 30

// The tier names for the legend, in the order they are shown. Each name also
// picks its color: "urgent" uses the .tier-urgent rule in App.css, and so on.
const TIER_NAMES = ['unresolved', 'monitor', 'repeat', 'consult', 'urgent']

// The gap between the numbers on the ONSD chart's y-axis, in mm.
const ONSD_TICK_STEP = 0.5

// Words in the backend's names that read better in capitals, for the Run info panel.
const ACRONYMS = ['onsd', 'hrv', 'ptt', 'sans', 'sd']

// The newest backend contract this page was built for. Data from a newer one
// gets a small warning, because its fields may have changed.
const SUPPORTED_SCHEMA_VERSION = '0.6.0'

// The measurement quality values that get the warning style on a card.
const POOR_QUALITY_VALUES = ['degraded', 'failed', 'unknown']

// Plain words for each tier_reason the backend can send. These only describe the
// backend's reason; they never decide anything.
const TIER_REASON_TEXT = {
  red_flag_symptom: 'A red-flag symptom was recorded.',
  measurement_quality: 'Set because of scan quality.',
  insufficient_evidence_for_probability:
    'Not enough evidence to estimate a probability. This does not mean low risk.',
  probability_threshold:
    'Set by comparing a simulated probability with the decision thresholds.',
}

// Plain words for why a capability in the manifest's capability_readiness list
// isn't ready.
const BLOCKED_STATE_TEXT = {
  blocked_missing_parameter: 'Missing a parameter',
  blocked_unapproved_assumption: 'Assumption not approved',
  blocked_missing_model_rule: 'No model rule yet',
  unsupported_scientific_use: 'Unsupported scientific use',
}

// The simulated Earth–Mars delay, for display only. To keep the demo short,
// 1 second of real time stands for 1 mission minute.
const DEFAULT_DELAY_MINUTES = 12
const MAX_DELAY_MINUTES = 20
const MS_PER_MISSION_MINUTE = 1000

// Every message has one of these two directions.
const CREW_TO_GROUND = 'Crew → Ground' // an update, carrying a snapshot of a record
const GROUND_TO_CREW = 'Ground → Crew' // a reply, carrying only an acknowledgement

// Compares the tiers on two records and describes any change, such as
// "Tier change: SANS repeat → urgent". SANS and Venous are checked separately,
// and each is named separately. It gives null if neither tier changed.
function describeTierChange(previousRecord, record) {
  const changes = []
  if (previousRecord.sans.tier !== record.sans.tier) {
    changes.push(`SANS ${previousRecord.sans.tier} → ${record.sans.tier}`)
  }
  if (previousRecord.venous.tier !== record.venous.tier) {
    changes.push(`Venous ${previousRecord.venous.tier} → ${record.venous.tier}`)
  }
  return changes.length > 0 ? `Tier change: ${changes.join(', ')}` : null
}

// A message has arrived once the current time reaches its arrival time.
function isDelivered(message, now) {
  return message.arrivesAt <= now
}

// Turns a time in milliseconds into a countdown such as "0:09". It rounds up,
// so the countdown only shows 0:00 at the moment the message arrives.
function formatCountdown(milliseconds) {
  const totalSeconds = Math.ceil(milliseconds / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  // padStart adds a leading zero when needed, so 9 becomes "09".
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

// Turns a timestamp into a clock time in the viewer's own format, like "14:05:09".
function formatClockTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

// JSONL means "one JSON object on each line". The file as a whole is not valid
// JSON, so we split it into lines and parse each line separately.
function parseJsonl(text) {
  const lines = text.split('\n')
  // A file usually ends with a newline, which leaves an empty last line.
  // JSON.parse would crash on an empty line, so we remove those first.
  const nonEmptyLines = lines.filter((line) => line.trim() !== '')
  return nonEmptyLines.map((line) => JSON.parse(line))
}

// Says why the backend gave this tier, in plain words. The tier and the reason
// are separate fields, and a "repeat" caused by scan quality must never read as
// a detected problem.
function describeTierReason(tier, reason) {
  // Older data files were written before this field existed.
  if (reason === null || reason === undefined) {
    return 'Reason not stated in this data file.'
  }
  if (tier === 'repeat' && reason === 'measurement_quality') {
    return 'Scan quality issue – not a sign of a detected problem.'
  }
  return TIER_REASON_TEXT[reason] ?? `Reason: ${readableName(reason)}.`
}

// Is this version newer than the baseline? The parts are compared as numbers,
// because compared as text, "0.10.0" would count as older than "0.6.0".
function isNewerVersion(version, baseline) {
  const toParts = (text) => String(text).split('.').map((part) => parseInt(part, 10) || 0)
  const versionParts = toParts(version)
  const baselineParts = toParts(baseline)

  for (let i = 0; i < Math.max(versionParts.length, baselineParts.length); i++) {
    const difference = (versionParts[i] ?? 0) - (baselineParts[i] ?? 0)
    if (difference !== 0) return difference > 0
  }
  return false
}

// Shows the backend's probability as a percentage, always with its label right
// next to it. Multiplying by 100 only changes how it's written; we never
// calculate a probability ourselves.
function ProbabilityText({ probability, label }) {
  // Check for null specifically. A shortcut like "if (!probability)" would
  // also treat a real value of 0 as missing, and we must not mix those up.
  // "undefined" is included because the schema lets the backend leave this out.
  if (probability === null || probability === undefined) {
    return <p>Unavailable. This does not mean zero risk; see the explanation below.</p>
  }

  // A number must never appear without its label, so we hold it back instead.
  if (!label?.trim()) {
    return <p>A probability was sent without its required label, so it is not shown.</p>
  }

  return (
    <p className="probability">
      <strong>{(probability * 100).toFixed(1)}%</strong>
      <span className="probability-label">{label}</span>
    </p>
  )
}

// One card for one outcome. We use this component twice, once for SANS and once
// for venous. The two are never combined, because the backend treats them as
// fully independent.
//   title   = the heading to show on the card
//   outcome = the "sans" or "venous" object from the selected day's record
function OutcomeCard({ title, outcome }) {
  const quality = outcome.measurement_quality
  const hasQuality = quality !== null && quality !== undefined

  return (
    <section className="card">
      <h2>{title}</h2>

      {/* The tier comes straight from the backend. Its name also picks the
          style: "urgent" uses the .tier-urgent rule in App.css, and so on. */}
      <p className={`tier-badge tier-${outcome.tier}`}>{outcome.tier}</p>

      <h3>Why this tier</h3>
      <p className="tier-reason">{describeTierReason(outcome.tier, outcome.tier_reason)}</p>

      {/* This section only appears when the backend gave us a quality value. */}
      {hasQuality && (
        <>
          <h3>Measurement quality</h3>
          <p>
            <span className={POOR_QUALITY_VALUES.includes(quality) ? 'quality-poor' : undefined}>
              {quality}
            </span>
          </p>
        </>
      )}

      <h3>Probability</h3>
      <ProbabilityText probability={outcome.probability} label={outcome.probability_label} />

      <h3>Explanation</h3>
      <p>{outcome.explanation}</p>

      <h3>Limitations</h3>
      {outcome.limitations.length === 0 ? (
        <p>None listed for this day.</p>
      ) : (
        <ul>
          {/* .map() turns each limitation into a list item. React needs a
              unique "key" on each item to keep track of the list. */}
          {outcome.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

// One row of the timeline, for one outcome. We use this component twice, once
// for SANS and once for venous, and each row only reads its own outcome. The
// two are never combined.
//   title            = the label to show above the row
//   outcomeKey       = which part of each record to read: "sans" or "venous"
//   astronautRecords = the selected astronaut's records, earliest day first
//   missionLength    = how many days the mission has, so how many boxes to show
//   selectedDay      = the day to highlight
//   onJump           = the function to call when the user clicks a box
function TimelineRow({ title, outcomeKey, astronautRecords, missionLength, selectedDay, onJump }) {
  // Build the list of days: 1, 2, 3... up to the mission length. Every day gets
  // a box, whether or not it has a record.
  const missionDays = Array.from({ length: missionLength }, (_, index) => index + 1)

  return (
    <div className="timeline-row">
      <h3>{title}</h3>
      <div className="timeline-boxes">
        {missionDays.map((day) => {
          // Find this day's position in the list. findIndex gives -1 if the
          // astronaut has no record for this day.
          const recordIndex = astronautRecords.findIndex(
            (record) => record.as_of_day === day,
          )

          // No record: show an empty box. It is not a button, because there
          // is nothing to jump to.
          if (recordIndex === -1) {
            const text = `Day ${day}: no record`
            return (
              <span
                key={day}
                className="timeline-box timeline-empty"
                role="img"
                title={text}
                aria-label={`${title}, ${text}`}
              />
            )
          }

          // The tier comes straight from the backend's record for this day.
          const tier = astronautRecords[recordIndex][outcomeKey].tier
          const isSelected = day === selectedDay
          const text = `Day ${day}: ${tier}`

          return (
            <button
              key={day}
              type="button"
              className={`timeline-box tier-${tier} ${isSelected ? 'timeline-selected' : ''}`}
              // "title" is the tooltip the browser shows on hover.
              title={text}
              // Screen readers can't see colors, so this says it in words.
              aria-label={`${title}, ${text}`}
              aria-current={isSelected}
              onClick={() => onJump(recordIndex)}
            />
          )
        })}
      </div>
    </div>
  )
}

// The small key that says what each box color means.
function TimelineLegend() {
  return (
    <ul className="timeline-legend">
      {TIER_NAMES.map((tier) => (
        <li key={tier}>
          <span className={`legend-swatch tier-${tier}`} />
          {tier}
        </li>
      ))}
      <li>
        <span className="legend-swatch timeline-empty" />
        no record
      </li>
    </ul>
  )
}

// Reads one observation's ONSD reading. A failed scan never has a value on the
// chart, even if the file gave it one, and a scan of another type isn't an ONSD
// scan at all, so its quality says nothing about ONSD.
function readOnsdScan(observation) {
  const scan = observation?.scan?.type === 'onsd' ? observation.scan : null
  const quality = scan?.quality?.status ?? null
  return {
    onsdMm: quality === 'failed' ? null : (scan?.onsd_mm ?? null),
    quality: quality,
  }
}

// Works out the y-axis from every astronaut's values, so the scale stays the same
// when switching astronauts. This only sizes the axis: it rounds outward to the
// nearest tick and is never shown or used as a reference value. It gives null if
// the file has no values to plot.
//   failedLane = the height for the ✕ markers, below the lowest tick, so a marker
//                can't be read as a measurement
function getOnsdAxis(observations) {
  const values = observations
    .map((observation) => readOnsdScan(observation).onsdMm)
    .filter((value) => value !== null)
  if (values.length === 0) return null

  const lowest = Math.floor(Math.min(...values) / ONSD_TICK_STEP) * ONSD_TICK_STEP
  const highest = Math.max(
    Math.ceil(Math.max(...values) / ONSD_TICK_STEP) * ONSD_TICK_STEP,
    lowest + ONSD_TICK_STEP,
  )
  const tickCount = Math.round((highest - lowest) / ONSD_TICK_STEP) + 1

  return {
    domain: [lowest - ONSD_TICK_STEP / 2, highest],
    ticks: Array.from({ length: tickCount }, (_, index) => lowest + index * ONSD_TICK_STEP),
    failedLane: lowest - ONSD_TICK_STEP / 4,
  }
}

// One round dot on the line: solid for "ok", and hollow amber for anything else
// that has a value, so a scan is never shown as ok unless the backend said so.
function OnsdDot({ cx, cy, payload }) {
  if (cy === null || cy === undefined) return null
  const style = payload.quality === 'ok' ? 'onsd-dot-solid' : 'onsd-dot-hollow'
  return <circle cx={cx} cy={cy} r={4} className={style} />
}

// One small ✕ for a failed scan, drawn as two crossing lines.
function FailedMarker({ cx, cy }) {
  if (cy === null || cy === undefined) return null
  return (
    <path
      d={`M${cx - 4} ${cy - 4} L${cx + 4} ${cy + 4} M${cx - 4} ${cy + 4} L${cx + 4} ${cy - 4}`}
      className="onsd-failed"
    />
  )
}

// The words for one row's value and quality. The tooltip and the table both use
// these, so they always say the same thing.
function onsdValueText(row) {
  return row.onsdMm === null ? 'No value' : `${row.onsdMm.toFixed(2)} mm`
}

function onsdQualityText(row) {
  return row.quality === null ? 'No scan' : row.quality.replace('_', ' ')
}

// The box that appears when hovering over or tapping a day on the chart.
function OnsdTooltip({ active, payload }) {
  // Both lines share the same row of data, so the first one is enough.
  const row = payload?.[0]?.payload
  if (!active || !row) return null

  return (
    <div className="onsd-tooltip">
      <div>
        <strong>Day {row.day}</strong>
      </div>
      {row.isFuture ? (
        <div>Not reached yet</div>
      ) : (
        <>
          <div>ONSD: {onsdValueText(row)}</div>
          <div>Quality: {onsdQualityText(row)}</div>
        </>
      )}
    </div>
  )
}

// The chart's values as a table, closed until the user opens it. This gives
// screen readers and anyone who can't use the tooltip the same information.
//   rows = only the days reached so far, so this can't show a later day either
function OnsdTable({ rows }) {
  return (
    <details className="onsd-values">
      <summary>Show values as a table</summary>
      <table>
        <thead>
          <tr>
            <th scope="col">Day</th>
            <th scope="col">ONSD</th>
            <th scope="col">Quality</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.day}>
              <td>{row.day}</td>
              <td>{onsdValueText(row)}</td>
              <td>{onsdQualityText(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

// The key that says what each marker means.
function OnsdLegend() {
  return (
    <ul className="timeline-legend onsd-legend">
      <li>
        <svg className="onsd-swatch" viewBox="0 0 12 12" aria-hidden="true">
          <circle cx="6" cy="6" r="4" className="onsd-dot-solid" />
        </svg>
        OK
      </li>
      <li>
        <svg className="onsd-swatch" viewBox="0 0 12 12" aria-hidden="true">
          <circle cx="6" cy="6" r="4" className="onsd-dot-hollow" />
        </svg>
        Degraded or unknown
      </li>
      <li>
        <svg className="onsd-swatch" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 2 L10 10 M2 10 L10 2" className="onsd-failed" />
        </svg>
        Failed (no value)
      </li>
      <li>Gap in the line: no value that day</li>
      <li>Days after the selected day stay hidden</li>
    </ul>
  )
}

// The ONSD chart for one astronaut. Every value comes straight from the file; we
// calculate no baseline, average, threshold or trend.
//   observations  = every record from the observations file, or null if not loaded
//   loadFailed    = true if that file couldn't be loaded
//   astronautId   = whose scans to show
//   missionLength = how many days the x-axis covers
//   selectedDay   = where to draw the vertical marker, which follows playback. No
//                   scan after this day is shown, because it hasn't happened yet
function OnsdChart({ observations, loadFailed, astronautId, missionLength, selectedDay }) {
  const axis = observations && getOnsdAxis(observations)

  // One row per mission day, whether or not it has a scan. A row whose value is
  // null is what makes the gap in the line. Later days are never looked up, so
  // the rows hold nothing about them.
  const rows = Array.from({ length: missionLength }, (_, index) => {
    const day = index + 1
    const isFuture = day > selectedDay
    const observation = isFuture
      ? undefined
      : observations?.find(
          (record) => record.astronaut_id === astronautId && record.day === day,
        )
    const { onsdMm, quality } = readOnsdScan(observation)
    return {
      day: day,
      isFuture: isFuture,
      onsdMm: onsdMm,
      quality: quality,
      failedMarker: quality === 'failed' ? axis?.failedLane : null,
    }
  })

  // Day 1, then every 5 days, so the labels still fit on a phone.
  const dayTicks = [1, ...rows.map((row) => row.day).filter((day) => day % 5 === 0)]

  return (
    <section className="onsd">
      <h2>ONSD trend</h2>

      {loadFailed && <p>Could not load the ONSD scans.</p>}
      {!loadFailed && !observations && <p>Loading ONSD scans…</p>}
      {observations && !axis && <p>This file has no ONSD values to plot.</p>}

      {axis && (
        <>
          <OnsdLegend />
          <div className="onsd-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 30, right: 20, bottom: 4, left: 0 }}>
                <CartesianGrid vertical={false} stroke="#9ca3af" strokeOpacity={0.35} />
                <XAxis
                  dataKey="day"
                  type="number"
                  domain={[1, missionLength]}
                  ticks={dayTicks}
                  // Keeps day 1's dot and marker from sitting on the y-axis.
                  padding={{ left: 10, right: 10 }}
                  height={48}
                  stroke="#9ca3af"
                  tick={{ fill: 'currentColor', fontSize: 12 }}
                  tickLine={false}
                  label={{
                    value: 'Mission day',
                    position: 'insideBottom',
                    fill: 'currentColor',
                    fontSize: 13,
                  }}
                />
                <YAxis
                  domain={axis.domain}
                  ticks={axis.ticks}
                  width={52}
                  stroke="#9ca3af"
                  tick={{ fill: 'currentColor', fontSize: 12 }}
                  tickLine={false}
                  tickFormatter={(value) => value.toFixed(1)}
                  label={{
                    value: 'ONSD (mm)',
                    angle: -90,
                    position: 'insideLeft',
                    style: { textAnchor: 'middle' },
                    fill: 'currentColor',
                    fontSize: 13,
                  }}
                />

                {/* filterNull={false} keeps the tooltip working on days with no value. */}
                <Tooltip
                  content={OnsdTooltip}
                  filterNull={false}
                  cursor={{ stroke: '#9ca3af' }}
                  isAnimationActive={false}
                />

                <ReferenceLine
                  x={selectedDay}
                  stroke="currentColor"
                  strokeWidth={1.5}
                  label={{
                    value: `Day ${selectedDay}`,
                    position: 'top',
                    // Lifts the label clear of the y-axis's top number.
                    offset: 12,
                    fill: 'currentColor',
                    fontSize: 12,
                  }}
                />

                {/* connectNulls={false} is what leaves a gap at a null, and
                    "linear" draws straight lines, so no curve suggests values
                    between scans. */}
                <Line
                  dataKey="onsdMm"
                  type="linear"
                  connectNulls={false}
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={OnsdDot}
                  activeDot={false}
                  isAnimationActive={false}
                />

                {/* The ✕ markers. This "line" is invisible and only places them. */}
                <Line
                  dataKey="failedMarker"
                  stroke="none"
                  dot={FailedMarker}
                  activeDot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <OnsdTable rows={rows.filter((row) => !row.isFuture)} />
        </>
      )}

      <p className="hint onsd-note">
        Simulated values. Shown against no personal baseline yet – baseline band not
        provided by the backend.
      </p>
    </section>
  )
}

// The SANS and Venous cards for one record. Both panels use this, so the crew
// and the ground always display a record in exactly the same way.
function RecordCards({ record }) {
  return (
    <div className="cards">
      <OutcomeCard title="SANS" outcome={record.sans} />
      <OutcomeCard title="Venous" outcome={record.venous} />
    </div>
  )
}

// The left panel: what the crew sees now, plus the button to send it to Earth.
//   record           = the record for the selected day
//   messages         = every message sent so far, in both directions
//   now              = the current time, used to work out each message's status
//   onSend           = the function to call when the user presses the button
//   autoSend         = is "Auto-send on tier change" ticked?
//   onAutoSendChange = the function to call when the user changes the checkbox
function CrewPanel({ record, messages, now, onSend, autoSend, onAutoSendChange }) {
  const hasMessageInTransit = messages.some((message) => !isDelivered(message, now))
  const replies = messages.filter((message) => message.direction === GROUND_TO_CREW)
  const repliesInTransit = replies.filter((reply) => !isDelivered(reply, now))
  const repliesDelivered = replies.filter((reply) => isDelivered(reply, now))

  return (
    <section className="panel panel-crew">
      <h2>Crew (onboard)</h2>

      <button type="button" className="send-button" onClick={onSend}>
        Send update to Earth
      </button>

      <label className="auto-send">
        <input
          type="checkbox"
          checked={autoSend}
          onChange={(event) => onAutoSendChange(event.target.checked)}
        />{' '}
        Auto-send on tier change
      </label>

      {hasMessageInTransit && (
        <p className="hint">Playback is paused while a message is in transit.</p>
      )}

      {repliesInTransit.map((reply) => (
        <IncomingMessage
          key={reply.number}
          label="Incoming reply"
          message={reply}
          now={now}
        />
      ))}

      {repliesDelivered.map((reply) => {
        // The update this reply answers. Adding the two delays gives the round
        // trip. Time spent waiting for someone to press Acknowledge isn't counted.
        const update = messages.find((message) => message.number === reply.repliesTo)
        const roundTripMs = update.delayMs + reply.delayMs

        return (
          <div className="reply" key={reply.number}>
            <p>{reply.text}</p>
            <p className="reply-status">
              Acknowledged by ground at {formatClockTime(reply.sentAt)}
            </p>
            <p className="hint">
              Round trip: {roundTripMs / MS_PER_MISSION_MINUTE} min (simulated)
            </p>
          </div>
        )
      })}

      <RecordCards record={record} />
    </section>
  )
}

// The countdown and progress bar for one message on its way. It doesn't show
// the message's contents, because the receiver can't know those until it arrives.
//   label = what is on its way, such as "Incoming update"
function IncomingMessage({ label, message, now }) {
  const timeLeft = message.arrivesAt - now

  return (
    <div className="incoming">
      <p>
        {label} – arrives in {formatCountdown(timeLeft)}
      </p>
      <progress
        aria-label={`Progress of the ${label.toLowerCase()}`}
        max={message.delayMs}
        value={message.delayMs - timeLeft}
      />
    </div>
  )
}

// The right panel: what Earth knows, which is only what has already arrived.
//   messages      = every message sent so far, in both directions
//   now           = the current time, used to work out each message's status
//   isFixture     = true if the data is hand-made test data
//   onAcknowledge = the function to call when the user presses Acknowledge
function GroundPanel({ messages, now, isFixture, onAcknowledge }) {
  const updates = messages.filter((message) => message.direction === CREW_TO_GROUND)
  const inTransit = updates.filter((update) => !isDelivered(update, now))
  const delivered = updates.filter((update) => isDelivered(update, now))

  // Delivered updates that nobody has replied to yet.
  const waitingForAcknowledge = delivered.filter(
    (update) => !messages.some((message) => message.repliesTo === update.number),
  )

  // The last received update is the one with the latest arrival time. Sorting
  // puts that one at the end of the list, and .at(-1) takes the last item. It
  // gives "undefined" when nothing has arrived yet.
  const lastReceived = delivered.sort((a, b) => a.arrivesAt - b.arrivesAt).at(-1)

  return (
    <section className="panel panel-ground">
      <h2>Ground (Earth)</h2>

      {/* This panel can be far from the top banner on a phone, so it carries
          its own copy of the labels. */}
      <p className="banner">SYNTHETIC – NOT REAL ASTRONAUT DATA</p>
      {isFixture && (
        <p className="fixture-warning">
          Engineering test data – not a simulation result.
        </p>
      )}

      {inTransit.map((update) => (
        <IncomingMessage
          key={update.number}
          label="Incoming update"
          message={update}
          now={now}
        />
      ))}

      {waitingForAcknowledge.map((update) => (
        <p className="acknowledge" key={update.number}>
          Update for Day {update.day}{' '}
          <button type="button" onClick={() => onAcknowledge(update)}>
            Acknowledge
          </button>
        </p>
      ))}

      {lastReceived ? (
        <>
          <p className="received-label">
            Last received: Day {lastReceived.snapshot.as_of_day}, sent at{' '}
            {formatClockTime(lastReceived.sentAt)}
          </p>
          <p>Astronaut: {lastReceived.snapshot.astronaut_id}</p>
          <RecordCards record={lastReceived.snapshot} />
        </>
      ) : (
        <p className="received-label">No update received yet</p>
      )}
    </section>
  )
}

// One labelled value in the message log.
function LogField({ label, children }) {
  return (
    <div>
      <span className="log-label">{label}</span>
      <span className="log-value">{children}</span>
    </div>
  )
}

// The list of every message in both directions, newest first.
function MessageLog({ messages, now }) {
  // Messages are stored oldest first. [...messages] makes a copy to reverse,
  // because .reverse() would otherwise change the original list.
  const newestFirst = [...messages].reverse()

  return (
    <section className="log">
      <h2>Message log</h2>

      {messages.length === 0 && <p>No messages yet.</p>}

      <ol className="log-list">
        {newestFirst.map((message) => (
          <li className="log-entry" key={message.number}>
            <LogField label="Direction">{message.direction}</LogField>
            <LogField label="Day">{message.day}</LogField>
            <LogField label="Reason">{message.reason}</LogField>
            <LogField label="Sent">{formatClockTime(message.sentAt)}</LogField>
            <LogField label="Delay">
              {message.delayMs / MS_PER_MISSION_MINUTE} min
            </LogField>
            <LogField label="Status">
              {isDelivered(message, now)
                ? 'Delivered'
                : `In transit ${formatCountdown(message.arrivesAt - now)}`}
            </LogField>
          </li>
        ))}
      </ol>
    </section>
  )
}

// How many days the backend counted at each tier, for one outcome. We use this
// twice, and SANS and Venous are never added together.
//   title  = the label to show before the counts
//   counts = an object such as { unresolved: 240 }, exactly as in the file
function TierCounts({ title, counts }) {
  // Object.entries turns { unresolved: 240 } into a list: [['unresolved', 240]].
  // "?? {}" gives an empty list if the file left this part out.
  const entries = Object.entries(counts ?? {})

  return (
    <div className="run-counts">
      <h4>{title}</h4>
      <ul className="timeline-legend">
        {entries.map(([tier, count]) => (
          <li key={tier}>
            <span className={`legend-swatch tier-${tier}`} />
            {tier}: {count}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Turns a backend name such as "daily_hrv_weak_signal" into "Daily HRV weak signal".
function readableName(name) {
  const words = name
    .split('_')
    .map((word) => (ACRONYMS.includes(word) ? word.toUpperCase() : word))
    .join(' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

// Makes one of the manifest's blocked reasons short enough to read in one line.
// This only changes how the backend's words are shown, never what they decide.
function readableReason(reason) {
  // Many reasons look like: blocked: assumption(s) not approved: ['some_name']
  // The parentheses in this pattern capture the part between the [ and ].
  const match = reason.match(/not approved: \[(.*)\]/)
  if (match) {
    const names = match[1]
      .split(',')
      .map((name) => readableName(name.replace(/['\s]/g, ''))) // removes quotes and spaces
    return `Assumption not approved: ${names.join(', ')}`
  }

  // Any other reason is written as sentences, so we show only the first one.
  return reason.split('. ')[0]
}

// Makes a blocker's message safe to put on screen. Some messages quote counts from
// the hidden ground truth, such as "(ground-truth status counts: {...})", and the
// handoff docs say those must never reach the page. Everything else is the
// backend's own wording.
function readableBlockerMessage(message) {
  return message.replace(/\s*\([^)]*ground[- ]truth[^)]*\)/gi, '')
}

// The "adaptive vs fixed" section at the bottom of the page. It only repeats what
// the backend's report says. It never calculates or shows a result of its own.
//   report     = the contents of evaluation_blockers.json, or null if not loaded
//   loadFailed = true if that file couldn't be loaded
function ResultsSection({ report, loadFailed }) {
  const blockers = report?.blockers ?? []

  return (
    <section className="results">
      <h2>Results: adaptive vs fixed scanning</h2>
      <p>
        This will compare scanning on a fixed 7-day schedule with scanning when the
        system flags a need, and find how reliable the daily signal must be for
        adaptive scanning to win.
      </p>

      {loadFailed && <p className="results-notice">Results file not found</p>}
      {!loadFailed && !report && <p>Loading results…</p>}

      {report && blockers.length === 0 && (
        <p className="results-notice">This file lists no blockers and holds no results to show.</p>
      )}

      {blockers.length > 0 && (
        <div className="results-notice">
          <p>
            Comparison not yet available – the backend refuses to produce this result
            until these are resolved:
          </p>
          <ul>
            {blockers.map((blocker) => (
              <li key={blocker.capability}>
                <strong>{readableName(blocker.capability)}:</strong>{' '}
                {readableBlockerMessage(blocker.message)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

// One label and value in the run info list. If the manifest left this value out,
// it says so instead of leaving a blank.
function RunFact({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value ?? 'Not stated'}</dd>
    </div>
  )
}

// The manifest's capability_readiness list, split into ready and blocked. Anything
// that isn't exactly "ready" goes under Blocked, including any state added later,
// so this list can never overstate what is ready.
//   readiness = an object such as { onsd_scan_values: 'ready' }, or undefined in
//               a manifest from before v0.6.0
function CapabilityReadiness({ readiness }) {
  if (!readiness) {
    return (
      <>
        <h3>Capability readiness</h3>
        <p>Not stated in this run's manifest.</p>
      </>
    )
  }

  const entries = Object.entries(readiness)
  const ready = entries.filter(([, state]) => state === 'ready')
  const blocked = entries.filter(([, state]) => state !== 'ready')

  return (
    <>
      <h3>Capability readiness</h3>
      <p className="hint">
        These are engineering states. Ready means the simulation can generate this
        value, not that the value is clinically validated.
      </p>
      <div className="run-capabilities">
        <div>
          <h4>Ready ({ready.length})</h4>
          <ul className="run-reasons">
            {ready.map(([capability]) => (
              <li key={capability}>{readableName(capability)}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Blocked ({blocked.length})</h4>
          <ul className="run-reasons">
            {blocked.map(([capability, state]) => (
              <li key={capability}>
                <strong>{readableName(capability)}:</strong>{' '}
                {BLOCKED_STATE_TEXT[state] ?? readableName(state)}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  )
}

// The collapsible "Run info" panel. <details> is built into the browser, and it
// opens and closes by itself when the title is clicked, so we need no state.
// Everything shown comes from the two files; we calculate no risk or tier.
//
// The manifest also holds fields such as scenario_counts. This panel only reads
// the fields below, so those are never shown.
//   manifest = the selected file's manifest, or null if it couldn't be read
//   summary  = the selected file's scoring summary, or null if it has none
function RunInfo({ manifest, summary }) {
  // "?? {}" gives an empty list if the manifest left the reasons out, which the
  // schema allows.
  const reasons = Object.entries(manifest?.physiological_generation_blocked_reasons ?? {})

  return (
    <details className="run-info">
      <summary>Run info</summary>

      {!manifest && <p>Could not read the run information from the manifest.</p>}

      {manifest && (
        <>
          <dl className="run-facts">
            <RunFact label="Run ID" value={manifest.run_id} />
            <RunFact label="Crew size" value={manifest.crew_size} />
            <RunFact label="Mission length (days)" value={manifest.mission_duration_days} />
            <RunFact
              label="Generation status"
              value={manifest.generation_status && readableName(manifest.generation_status)}
            />
          </dl>

          <CapabilityReadiness readiness={manifest.capability_readiness} />

          <h3>Why these values are blocked</h3>
          {reasons.length === 0 ? (
            <p>No reasons listed.</p>
          ) : (
            <ul className="run-reasons">
              {reasons.map(([capability, reason]) => (
                <li key={capability}>
                  <strong>{readableName(capability)}:</strong> {readableReason(reason)}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {summary && (
        <>
          <h3>Tier counts (all astronauts, all days)</h3>
          <p>
            Astronauts scored: {summary.astronauts_scored}. Days scored: {summary.days_scored}.
          </p>
          {summary.errors?.length > 0 && (
            <p>Scoring errors reported: {summary.errors.length}</p>
          )}
          <TierCounts title="SANS" counts={summary.sans_tier_distribution} />
          <TierCounts title="Venous" counts={summary.venous_tier_distribution} />

          <h3>Days with a computed probability</h3>
          <dl className="run-facts">
            <RunFact label="SANS" value={summary.sans_probability_computed_count} />
            <RunFact label="Venous" value={summary.venous_probability_computed_count} />
          </dl>

          <h3>Structural warnings</h3>
          {!summary.structural_warnings && <p>Not stated in this summary.</p>}
          {summary.structural_warnings?.length === 0 && <p>None reported.</p>}
          {summary.structural_warnings?.length > 0 && (
            <>
              <p className="hint">
                Data-quality flags, not errors. These days were still scored.
              </p>
              <ul className="run-reasons">
                {summary.structural_warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </>
          )}

          {summary.note && <p className="run-note">{summary.note}</p>}
        </>
      )}
    </details>
  )
}

// The main page. React re-runs this function whenever a state value changes.
function App() {
  // Each useState gives us the current value and a function to change it.
  const [fileUrl, setFileUrl] = useState(DATA_FILES[0].url) // the chosen file
  const [records, setRecords] = useState([]) // all records from that file
  const [chosenAstronaut, setChosenAstronaut] = useState(null) // null = nobody picked yet
  const [dayIndex, setDayIndex] = useState(0) // position on the slider (see below)
  const [isLoading, setIsLoading] = useState(true) // is the file still loading?
  const [errorMessage, setErrorMessage] = useState(null) // what went wrong, if anything
  const [isPlaying, setIsPlaying] = useState(false) // is playback running?
  const [speed, setSpeed] = useState(PLAYBACK_SPEEDS[0]) // playback speed: 1, 2 or 4
  const [missionLength, setMissionLength] = useState(null) // null = not known yet
  const [usedFallback, setUsedFallback] = useState(false) // did we have to use the fallback?
  const [runManifest, setRunManifest] = useState(null) // null = none loaded
  const [runSummary, setRunSummary] = useState(null) // null = none loaded
  const [summaryFailed, setSummaryFailed] = useState(false) // did the summary fail to load?
  const [observations, setObservations] = useState(null) // null = none loaded
  const [observationsFailed, setObservationsFailed] = useState(false) // did they fail to load?
  const [resultsReport, setResultsReport] = useState(null) // null = not loaded
  const [resultsFailed, setResultsFailed] = useState(false) // did the report fail to load?
  const [delayMinutes, setDelayMinutes] = useState(DEFAULT_DELAY_MINUTES) // the delay slider
  const [messages, setMessages] = useState([]) // every message so far, oldest first
  const [now, setNow] = useState(0) // the current time, updated while messages travel
  const [autoSend, setAutoSend] = useState(true) // the "Auto-send on tier change" checkbox

  // Is any message still on its way? This is worked out from the arrival times,
  // so a message's status can never disagree with its countdown.
  const hasMessageInTransit = messages.some((message) => !isDelivered(message, now))

  // While a message is on its way, update "now" 10 times a second. Each update
  // refreshes the countdowns, and a message becomes delivered as soon as "now"
  // reaches its arrival time. The timer stops when nothing is left in transit.
  useEffect(() => {
    if (!hasMessageInTransit) return

    const timer = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(timer)
  }, [hasMessageInTransit])

  // Read the chosen file's mission length. The [fileUrl] at the end means "run
  // this when the page opens, and again whenever fileUrl changes".
  useEffect(() => {
    // Marks this load as out of date if the user switches files, like the
    // data file load below.
    let isCurrent = true

    function applyFallbackLength() {
      if (!isCurrent) return
      setMissionLength(FALLBACK_MISSION_LENGTH)
      setUsedFallback(true)
    }

    const { manifestUrl } = DATA_FILES.find((file) => file.url === fileUrl)

    fetch(manifestUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.json() // the manifest is ordinary JSON, not JSONL
      })
      .then((manifest) => {
        if (!isCurrent) return
        const length = manifest.mission_duration_days
        setRunManifest(manifest)
        // Only accept a whole number above 0. Anything else, including a
        // missing field, can't be used as a number of days.
        if (Number.isInteger(length) && length > 0) {
          setMissionLength(length)
        } else {
          applyFallbackLength()
        }
      })
      // This catches a failed download and a file that isn't valid JSON.
      .catch(applyFallbackLength)

    return () => {
      isCurrent = false
    }
  }, [fileUrl])

  // Read the chosen file's run summary, if it has one.
  useEffect(() => {
    const { summaryUrl } = DATA_FILES.find((file) => file.url === fileUrl)
    if (!summaryUrl) return

    let isCurrent = true

    fetch(summaryUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.json()
      })
      .then((summary) => {
        if (isCurrent) setRunSummary(summary)
      })
      .catch(() => {
        if (isCurrent) setSummaryFailed(true)
      })

    return () => {
      isCurrent = false
    }
  }, [fileUrl])

  // Read the evaluation report once, when the page opens. It doesn't depend on the
  // chosen data file. When a file is missing, the dev server may send the page's
  // HTML instead of a 404, so a reply that isn't valid JSON counts as a failure too.
  useEffect(() => {
    let isCurrent = true

    fetch('/data/evaluation_blockers.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.json()
      })
      .then((report) => {
        if (isCurrent) setResultsReport(report)
      })
      .catch(() => {
        if (isCurrent) setResultsFailed(true)
      })

    return () => {
      isCurrent = false
    }
  }, [])

  // Read the chosen file's scans for the ONSD chart, if it has any.
  useEffect(() => {
    const { observationsUrl } = DATA_FILES.find((file) => file.url === fileUrl)
    if (!observationsUrl) return

    let isCurrent = true

    fetch(observationsUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.text()
      })
      .then((text) => {
        if (isCurrent) setObservations(parseJsonl(text))
      })
      .catch(() => {
        if (isCurrent) setObservationsFailed(true)
      })

    return () => {
      isCurrent = false
    }
  }, [fileUrl])

  // Load the chosen file. The [fileUrl] at the end means "run this when the
  // page opens, and again whenever fileUrl changes".
  useEffect(() => {
    // If the user switches files while one is still loading, the older file
    // could finish last and replace the newer one. The cleanup function below
    // marks the older load as out of date, so its result is ignored.
    let isCurrent = true

    fetch(fileUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.text() // read the file as plain text
      })
      .then((text) => {
        if (isCurrent) setRecords(parseJsonl(text))
      })
      .catch((error) => {
        if (isCurrent) setErrorMessage(error.message)
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false)
      })

    return () => {
      isCurrent = false
    }
  }, [fileUrl])

  // Runs when the user picks another file. The old file's records, astronaut,
  // day and messages don't apply to the new file, so we clear them all. The
  // ground snapshot comes from the messages, so it is cleared with them.
  function handleFileChange(event) {
    setIsPlaying(false)
    setMessages([])
    setFileUrl(event.target.value)
    setRecords([])
    setChosenAstronaut(null)
    setDayIndex(0)
    setIsLoading(true)
    setErrorMessage(null)
    setMissionLength(null)
    setUsedFallback(false)
    setRunManifest(null)
    setRunSummary(null)
    setSummaryFailed(false)
    setObservations(null)
    setObservationsFailed(false)
  }

  // Runs when the user picks another astronaut. Their days may be different,
  // so we go back to their first available day. The messages belong to the
  // previous astronaut, so we clear those too.
  function handleAstronautChange(event) {
    setIsPlaying(false)
    setMessages([])
    setChosenAstronaut(event.target.value)
    setDayIndex(0)
  }

  // The values below are worked out fresh from the state each time the page
  // updates. They only look records up; every tier and text comes straight
  // from the backend's file.
  const selectedFile = DATA_FILES.find((file) => file.url === fileUrl)

  // Today's scored records have no metadata block, so the manifest's own
  // schema_version is what normally gives this run's version. Records are
  // checked too, in case they carry one.
  const newerSchemaVersion = [
    ...records.map((record) => record.metadata?.schema_version),
    runManifest?.schema_version,
  ].find((version) => version && isNewerVersion(version, SUPPORTED_SCHEMA_VERSION))

  // A Set keeps only one copy of each value, which gives us each astronaut once.
  // The pipeline's file isn't in astronaut order, so we sort the list to show
  // A1, A2, A3... in the dropdown.
  const astronautIds = [...new Set(records.map((record) => record.astronaut_id))].sort()

  // Until the user picks someone, use the first astronaut in the file.
  const astronautId = chosenAstronaut ?? astronautIds[0]

  // The page isn't ready until both the data file and the manifest have loaded.
  const isStillLoading = isLoading || missionLength === null

  // This astronaut's records within the mission length, from the earliest day
  // to the latest. The slider and the timeline both use this list, so they
  // always cover the same days.
  const astronautRecords = records
    .filter((record) => record.astronaut_id === astronautId)
    .filter((record) => record.as_of_day <= missionLength)
    .sort((a, b) => a.as_of_day - b.as_of_day)

  // The slider moves through positions in astronautRecords (0, 1, 2...) rather
  // than day numbers. That way it can only land on days that really exist,
  // even when there are gaps between them.
  const selectedRecord = isStillLoading ? undefined : astronautRecords[dayIndex]

  // The slider position of this astronaut's last day. Lists count from 0, so
  // with 30 days, the last position is 29.
  const lastDayIndex = astronautRecords.length - 1
  const hasOnlyOneDay = astronautRecords.length === 1

  // Adds one message to the list. Every message goes through here: updates sent
  // by the button, updates sent automatically, and replies from the ground. The
  // delay is stored in the message, so moving the delay slider later can't
  // change it.
  //   details = the parts that differ between messages, such as the reason
  function addMessage(details) {
    const sentAt = Date.now()

    // With a delay of 0, the message is never in transit, so nothing to pause.
    if (details.delayMs > 0) setIsPlaying(false)

    setNow(sentAt)
    setMessages([
      ...messages, // keep the existing messages, and add the new one at the end
      {
        ...details, // copy in everything from details
        number: messages.length + 1,
        sentAt: sentAt,
        arrivesAt: sentAt + details.delayMs,
      },
    ])
  }

  // Sends an update holding a record exactly as it came from the file.
  function sendUpdate(record, reason) {
    addMessage({
      direction: CREW_TO_GROUND,
      day: record.as_of_day,
      reason: reason,
      snapshot: record,
      delayMs: delayMinutes * MS_PER_MISSION_MINUTE,
    })
  }

  // Runs when the user moves to a new day by playback or with the slider. If a
  // tier differs from the previous available day, this sends an update.
  function autoSendIfTierChanged(newDayIndex) {
    if (!autoSend) return

    // The first available day has no previous day to compare with.
    const previousRecord = astronautRecords[newDayIndex - 1]
    if (!previousRecord) return

    const record = astronautRecords[newDayIndex]
    const reason = describeTierChange(previousRecord, record)
    if (!reason) return

    // Dragging the slider back and forth can land on the same day many times,
    // so only send the first time.
    const alreadySent = messages.some(
      (message) => message.day === record.as_of_day && message.reason === reason,
    )
    if (!alreadySent) sendUpdate(record, reason)
  }

  // One step of playback: move to the next day.
  const moveToNextDay = useEffectEvent(() => {
    const nextDayIndex = dayIndex + 1
    setDayIndex(nextDayIndex)
    // Stop as soon as we arrive at the last day.
    if (nextDayIndex >= lastDayIndex) setIsPlaying(false)
    autoSendIfTierChanged(nextDayIndex)
  })

  // While playing, wait, then move to the next day. Moving changes dayIndex,
  // which is listed at the end of this useEffect, so React runs it again and
  // starts the wait for the following day.
  useEffect(() => {
    if (!isPlaying) return

    const timer = setTimeout(() => moveToNextDay(), MS_PER_DAY_AT_1X / speed)

    // React runs this cleanup before the next run, and it cancels the pending
    // wait. This is how pausing stops the next step from happening.
    return () => clearTimeout(timer)
  }, [isPlaying, dayIndex, speed])

  // Runs when the user clicks the Play/Pause button.
  function handlePlayPause() {
    if (isPlaying) {
      setIsPlaying(false)
      return
    }
    // Pressing Play on the last day starts again from the first day.
    if (dayIndex === lastDayIndex) setDayIndex(0)
    setIsPlaying(true)
  }

  // Runs when the slider's value changes, by dragging or with the arrow keys.
  function handleSliderChange(event) {
    setIsPlaying(false)
    // A slider's value is always text, like "7", so we convert it to a number
    // before using it as a position in the list.
    const newDayIndex = Number(event.target.value)
    setDayIndex(newDayIndex)
    autoSendIfTierChanged(newDayIndex)
  }

  // Runs when the user clicks a timeline box. Like the slider, it pauses
  // playback. The box gives us the day's position in the list.
  function handleTimelineJump(recordIndex) {
    setIsPlaying(false)
    setDayIndex(recordIndex)
  }

  // Runs when the user presses Acknowledge on a delivered update. The reply uses
  // the same delay as that update, and its fixed sentence is all it ever says.
  function handleAcknowledge(update) {
    addMessage({
      direction: GROUND_TO_CREW,
      day: update.day,
      reason: 'Acknowledgement',
      text: `Ground acknowledges update for Day ${update.day}.`,
      repliesTo: update.number,
      delayMs: update.delayMs,
    })
  }

  // Runs when the user presses "Skip countdown". This delivers the oldest
  // message still in transit by moving its arrival time to right now. The list
  // is oldest first, so .find() gives the oldest match.
  function handleSkipCountdown() {
    const oldest = messages.find((message) => !isDelivered(message, now))
    if (!oldest) return

    const skippedAt = Date.now()
    setNow(skippedAt)
    setMessages(
      messages.map((message) =>
        message === oldest ? { ...message, arrivesAt: skippedAt } : message,
      ),
    )
  }

  return (
    <main className="page">
      {/* The handoff docs require this label on any screen showing this data,
          so it sits outside the conditions below and always appears. */}
      <p className="banner">SYNTHETIC – NOT REAL ASTRONAUT DATA</p>

      {selectedFile.isFixture && (
        <p className="fixture-warning">
          Engineering test data – not a simulation result.
        </p>
      )}

      {newerSchemaVersion && (
        <p className="schema-warning">
          This data uses schema {newerSchemaVersion}, which is newer than the{' '}
          {SUPPORTED_SCHEMA_VERSION} this page was built for. Some fields may not
          display correctly.
        </p>
      )}

      <h1>Fluid-Shift Monitoring</h1>

      <div className="controls">
        <label>
          Data file
          <select value={fileUrl} onChange={handleFileChange}>
            {DATA_FILES.map((file) => (
              <option key={file.url} value={file.url}>
                {file.label}
              </option>
            ))}
          </select>
        </label>

        {/* Only show this once there are astronauts to choose from. */}
        {astronautIds.length > 0 && (
          <label>
            Astronaut
            <select value={astronautId} onChange={handleAstronautChange}>
              {astronautIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {usedFallback && (
        <p className="small-note">
          Could not read the mission length from the manifest, so this page is
          using {FALLBACK_MISSION_LENGTH} days.
        </p>
      )}

      {/* Wait until the manifest has been read, so the panel doesn't first say it
          couldn't be read. The fixture is hand-made and didn't come from the run
          the manifest describes, so it doesn't get this panel. */}
      {missionLength !== null && !selectedFile.isFixture && (
        <RunInfo manifest={runManifest} summary={runSummary} />
      )}

      {summaryFailed && <p className="small-note">Could not load the run summary.</p>}

      {/* "condition && <something>" shows the something only if the condition
          is true. Only one of these four blocks appears at a time. */}
      {isStillLoading && <p>Loading data…</p>}

      {errorMessage && <p>Could not load the data: {errorMessage}</p>}

      {!isStillLoading && !errorMessage && !selectedRecord && (
        <p>No records to show within the {missionLength}-day mission.</p>
      )}

      {selectedRecord && (
        <>
          {/* htmlFor connects this label to the slider with the matching id. */}
          <label className="day-label" htmlFor="day-slider">
            Mission day: <strong>{selectedRecord.as_of_day}</strong>
            {hasOnlyOneDay && ' (the only day on record for this astronaut)'}
          </label>

          <div className="playback">
            <button
              type="button"
              onClick={handlePlayPause}
              disabled={hasOnlyOneDay || hasMessageInTransit}
            >
              {isPlaying ? 'Pause' : 'Play'}
            </button>

            <input
              id="day-slider"
              type="range"
              min={0}
              max={lastDayIndex}
              value={dayIndex}
              // With only one day, there is nowhere for the slider to go.
              disabled={hasOnlyOneDay}
              // The slider's value is a position, so this tells screen readers
              // the actual day number to announce.
              aria-valuetext={`Day ${selectedRecord.as_of_day}`}
              // Pause as soon as the user presses the slider, so the day
              // doesn't keep moving while they are holding it.
              onPointerDown={() => setIsPlaying(false)}
              onChange={handleSliderChange}
            />

            {/* Restart goes back to the first day. It doesn't change whether
                playback is running. */}
            <button type="button" onClick={() => setDayIndex(0)} disabled={hasOnlyOneDay}>
              Restart
            </button>

            <label>
              Speed{' '}
              <select
                value={speed}
                // A dropdown's value is also text, so we convert it to a number.
                onChange={(event) => setSpeed(Number(event.target.value))}
              >
                {PLAYBACK_SPEEDS.map((option) => (
                  <option key={option} value={option}>
                    {option}×
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="delay-control">
            <label htmlFor="delay-slider">
              One-way delay: <strong>{delayMinutes}</strong>{' '}
              {delayMinutes === 1 ? 'minute' : 'minutes'}
            </label>
            <input
              id="delay-slider"
              type="range"
              min={0}
              max={MAX_DELAY_MINUTES}
              value={delayMinutes}
              onChange={(event) => setDelayMinutes(Number(event.target.value))}
            />
            <p className="hint">Demo time: 1 second = 1 mission minute</p>
            {/* For demo rehearsals. */}
            <button
              type="button"
              className="skip-button"
              onClick={handleSkipCountdown}
              disabled={!hasMessageInTransit}
            >
              Skip countdown
            </button>
          </div>

          <div className="panels">
            <CrewPanel
              record={selectedRecord}
              messages={messages}
              now={now}
              onSend={() => sendUpdate(selectedRecord, 'Manual')}
              autoSend={autoSend}
              onAutoSendChange={setAutoSend}
            />
            <GroundPanel
              messages={messages}
              now={now}
              isFixture={selectedFile.isFixture}
              onAcknowledge={handleAcknowledge}
            />
          </div>

          <MessageLog messages={messages} now={now} />

          <section className="timeline">
            <h2>Timeline</h2>
            <TimelineRow
              title="SANS"
              outcomeKey="sans"
              astronautRecords={astronautRecords}
              missionLength={missionLength}
              selectedDay={selectedRecord.as_of_day}
              onJump={handleTimelineJump}
            />
            <TimelineRow
              title="Venous"
              outcomeKey="venous"
              astronautRecords={astronautRecords}
              missionLength={missionLength}
              selectedDay={selectedRecord.as_of_day}
              onJump={handleTimelineJump}
            />
            <TimelineLegend />
          </section>

          {/* Only a file with its own scans gets this chart, so one run's scans
              are never shown against another file's records. */}
          {selectedFile.observationsUrl && (
            <OnsdChart
              observations={observations}
              loadFailed={observationsFailed}
              astronautId={astronautId}
              missionLength={missionLength}
              selectedDay={selectedRecord.as_of_day}
            />
          )}
        </>
      )}

      <ResultsSection report={resultsReport} loadFailed={resultsFailed} />
    </main>
  )
}

export default App
