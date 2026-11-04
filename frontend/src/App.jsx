// useState lets a component remember a value between screen updates.
// useEffect lets a component run code after it first appears on screen.
import { useEffect, useState } from 'react'
import './App.css'

// Files in the "public" folder are served from the root of the website,
// so public/data/example.jsonl is available at /data/example.jsonl.
const DATA_URL = '/data/example_scored_blocked.jsonl'

// The mission lasts 30 days, so the slider goes from 1 to 30.
const FIRST_DAY = 1
const LAST_DAY = 30

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
  return (
    <section className="card">
      <h2>{title}</h2>

      <h3>Tier</h3>
      <p className="tier">{outcome.tier}</p>

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

// The main page. React re-runs this function whenever a state value changes.
function App() {
  // Each useState gives us the current value and a function to change it.
  const [records, setRecords] = useState([]) // all records from the file
  const [day, setDay] = useState(FIRST_DAY) // the day chosen on the slider
  const [isLoading, setIsLoading] = useState(true) // is the file still loading?
  const [errorMessage, setErrorMessage] = useState(null) // what went wrong, if anything

  // Load the file once when the page opens. The empty [] at the end of
  // useEffect means "do not run this again when the page updates".
  useEffect(() => {
    fetch(DATA_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server responded with status ${response.status}`)
        }
        return response.text() // read the file as plain text
      })
      .then((text) => setRecords(parseJsonl(text)))
      .catch((error) => setErrorMessage(error.message))
      .finally(() => setIsLoading(false))
  }, [])

  // Find the record for the selected day. This only looks the record up; all
  // tiers and text come straight from the backend's file.
  const selectedRecord = records.find((record) => record.as_of_day === day)

  return (
    <main className="page">
      {/* The handoff docs require this label on any screen showing this data,
          so it sits outside the conditions below and always appears. */}
      <p className="banner">SYNTHETIC – NOT REAL ASTRONAUT DATA</p>

      <h1>Fluid-Shift Monitoring</h1>

      <label className="day-picker">
        Mission day: <strong>{day}</strong>
        <input
          type="range"
          min={FIRST_DAY}
          max={LAST_DAY}
          value={day}
          // A slider's value is always text, like "7", so we convert it to a
          // number. Otherwise it would never match as_of_day above.
          onChange={(event) => setDay(Number(event.target.value))}
        />
      </label>

      {/* "condition && <something>" shows the something only if the condition
          is true. Exactly one of these four blocks appears at a time. */}
      {isLoading && <p>Loading data…</p>}

      {errorMessage && <p>Could not load the data: {errorMessage}</p>}

      {!isLoading && !errorMessage && !selectedRecord && (
        <p>No record found for day {day}.</p>
      )}

      {selectedRecord && (
        <>
          <p>Astronaut: {selectedRecord.astronaut_id}</p>
          <div className="cards">
            <OutcomeCard title="SANS" outcome={selectedRecord.sans} />
            <OutcomeCard title="Venous" outcome={selectedRecord.venous} />
          </div>
        </>
      )}
    </main>
  )
}

export default App
