import { useEffect, useState } from 'react'
import { DATA } from './constants.js'

// JSONL means one JSON object per line.
function parseJsonl(text) {
  return text
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => JSON.parse(line))
}

async function load(url, jsonl) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} (status ${response.status})`)
  return jsonl ? parseJsonl(await response.text()) : response.json()
}

// Loads the pipeline run once. The scored file is required; the others are
// optional, and the view shows what it can when one is missing.
export function useMissionData() {
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    const optional = (promise) => promise.catch(() => null)

    Promise.all([
      load(DATA.scored, true),
      optional(load(DATA.observations, true)),
      optional(load(DATA.manifest, false)),
      optional(load(DATA.evaluation, false)),
    ])
      .then(([scored, observations, manifest, evaluation]) => {
        if (!cancelled) setState({ status: 'ready', scored, observations, manifest, evaluation })
      })
      .catch((error) => {
        if (!cancelled) setState({ status: 'error', message: error.message })
      })

    return () => {
      cancelled = true
    }
  }, [])

  return state
}
