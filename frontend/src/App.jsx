// useState lets a component remember a value between screen updates.
// useEffect lets a component run code after it appears on screen.
// useEffectEvent makes a function that a useEffect can call, and that always
// sees the latest values without making the useEffect start over.
import { useEffect, useEffectEvent, useState } from 'react'
import './App.css'

// The data files the user can choose from. Files in the "public" folder are
// served from the root of the website, so public/data/example.jsonl is
// available at /data/example.jsonl.
//   label     = the text shown in the dropdown
//   url       = where to load the file from
//   isFixture = true for hand-made test data, which needs a warning on screen
const DATA_FILES = [
  {
    label: 'Pipeline output (blocked)',
    url: '/data/example_scored_blocked.jsonl',
    isFixture: false,
  },
  {
    label: 'UI test fixture',
    url: '/data/example_engineering_fixture_scored.jsonl',
    isFixture: true,
  },
]

// Mission playback: at 1× speed, each day stays on screen for 2000 milliseconds
// (2 seconds). At 2× it stays half as long, and at 4× a quarter as long.
const MS_PER_DAY_AT_1X = 2000
const PLAYBACK_SPEEDS = [1, 2, 4]

// The mission length comes from this file. If we can't get it from there, we
// use the fallback below and show a note saying so.
const MANIFEST_URL = '/data/example_simulation_manifest.json'
const FALLBACK_MISSION_LENGTH = 30

// The tier names for the legend, in the order they are shown. Each name also
// picks its color: "urgent" uses the .tier-urgent rule in App.css, and so on.
const TIER_NAMES = ['unresolved', 'monitor', 'repeat', 'consult', 'urgent']

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

// Shows the probability exactly as the backend sent it. We never calculate one.
function ProbabilityText({ probability }) {
  // Check for null specifically. A shortcut like "if (!probability)" would
  // also treat a real value of 0 as missing, and we must not mix those up.
  // "undefined" is included because the schema lets the backend leave this out.
  if (probability === null || probability === undefined) {
    return <p>Unavailable. This does not mean zero risk; see the explanation below.</p>
  }
  return <p>{probability}</p>
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

      {/* This section only appears when the backend gave us a quality value. */}
      {hasQuality && (
        <>
          <h3>Measurement quality</h3>
          <p>{quality}</p>
        </>
      )}

      <h3>Probability</h3>
      <ProbabilityText probability={outcome.probability} />

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

  // Read the mission length once when the page opens. The empty [] at the end
  // means "do not run this again when the page updates".
  useEffect(() => {
    function applyFallbackLength() {
      setMissionLength(FALLBACK_MISSION_LENGTH)
      setUsedFallback(true)
    }

    fetch(MANIFEST_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.json() // the manifest is ordinary JSON, not JSONL
      })
      .then((manifest) => {
        const length = manifest.mission_duration_days
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
  }, [])

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

  // A Set keeps only one copy of each value, which gives us each astronaut once.
  const astronautIds = [...new Set(records.map((record) => record.astronaut_id))]

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
        </>
      )}
    </main>
  )
}

export default App
