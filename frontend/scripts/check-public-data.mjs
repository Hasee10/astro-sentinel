import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

// fileURLToPath(), not `new URL(...).pathname` - the raw pathname of a
// file:// URL on Windows is "/D:/...", which Node's fs functions do not
// accept as a native path (observed failure: readdirSync resolved it to
// "D:\D:\...", a doubled drive letter). fileURLToPath() converts correctly
// on every platform this repo runs on.
const base = fileURLToPath(new URL('../public/data/pipeline/', import.meta.url))
const files = readdirSync(base)
const forbiddenNames = ['ground_truth', 'experiment_readiness_summary', 'run_status', 'pilot_info']
const forbiddenKeys = new Set(['scenario_counts', 'scenario_label', 'sans_onset_day', 'venous_onset_day', 'has_sans_event', 'has_venous_event', 'sans_event_occurs'])
const expected = ['crew_observations.jsonl', 'crew_scored.jsonl', 'simulation_manifest.json', 'evaluation_blockers.json']
const assert = (ok, message) => { if (!ok) throw new Error(message) }
for (const name of files) assert(!forbiddenNames.some(x => name.includes(x)), `Forbidden public file: ${name}`)
for (const name of expected) assert(files.includes(name), `Missing ${name}`)
const manifest = JSON.parse(readFileSync(join(base, 'simulation_manifest.json'), 'utf8'))
assert(manifest.run_id, 'Missing run ID in manifest')
const visit = (v, path) => {
  if (Array.isArray(v)) v.forEach((x, i) => visit(x, `${path}[${i}]`))
  else if (v && typeof v === 'object') for (const [k, val] of Object.entries(v)) {
    assert(!forbiddenKeys.has(k), `Hidden key ${path}.${k}`)
    visit(val, `${path}.${k}`)
  }
}
visit(manifest, 'manifest')
const rows = name => readFileSync(join(base, name), 'utf8').trim().split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line))
const obs = rows('crew_observations.jsonl')
const scored = rows('crew_scored.jsonl')
assert(obs.length > 0 && obs.length === scored.length, 'Observation/scored record count mismatch')
for (const [i, record] of obs.entries()) {
  visit(record, `observations[${i}]`)
  assert(record.metadata?.run_id === manifest.run_id, `Mixed run IDs in record ${i}`)
  assert(record.metadata?.synthetic === true, `Non-synthetic record ${i}`)
}
for (const [i, record] of scored.entries()) visit(record, `scored[${i}]`)
const evalData = JSON.parse(readFileSync(join(base,'evaluation_blockers.json'), 'utf8'))
visit(evalData, 'evaluation')

// Adapted from the handed-off version of this script, which required every
// blocker object's keys to be exactly {capability} - too strict for this
// repo: App.jsx's debug dashboard (preserved unchanged - see Root.jsx) reads
// blocker.message to explain WHY the experiment is blocked, and
// backend/publish_frontend_demo_data.py already sanitizes that text at the
// source rather than deleting it (see that script's own docstring). Some
// SAFE messages are also dict-shaped prose (e.g. venous_eligibility_conditions
// lists registry-approval booleans like {'event_occurrence_model_approved':
// False, ...} - public information, same as registry/design_decisions.py) -
// a blanket "no message may look like a dict" check would reject those too.
// The real invariant is narrower: no message may embed a dict keyed by one
// of evaluation/experiment_readiness.py's own EventGroundTruthStatus values
// (confirmed_none, confirmed_with_onset, event_unknown_onset, undetermined) -
// that exact shape (e.g. "{'confirmed_none': 5, 'event_unknown_onset': 3}")
// is what an unsanitized per-case ground-truth status-count leak looks like,
// and is what the original defect produced.
const GROUND_TRUTH_STATUS_WORDS = ['confirmed_none', 'confirmed_with_onset', 'event_unknown_onset', 'undetermined']
const STATUS_DICT_PATTERN = new RegExp(`\\{[^}]*'(${GROUND_TRUTH_STATUS_WORDS.join('|')})'`, 'i')
for (const blocker of evalData.blockers || []) {
  assert(typeof blocker.capability === 'string' && blocker.capability, 'Blocker missing capability')
  if (typeof blocker.message === 'string') {
    assert(
      !STATUS_DICT_PATTERN.test(blocker.message),
      `Blocker ${blocker.capability} message embeds a per-case ground-truth status count - looks like an unsanitized leak: ${blocker.message}`,
    )
  }
}

console.log(`Verified ${obs.length} public synthetic observation records and ${scored.length} scored records; run ${manifest.run_id}. No hidden ground-truth keys.`)
