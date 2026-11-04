# Integration Commands

Run from `backend/` on a machine with Python 3.10+ (the versions actually used to
build/test this handoff: pydantic 2.13, pytest 8.4, matplotlib 3.10).

```bash
# 0. Setup
pip install -r requirements.txt

# 1. Generate observation files (synthetic crew)
python generate_crew.py --crew-size 8 --seed 42 --output-dir outputs/run1

# 1b. Deterministic replay (byte-identical output across machines/runs)
python generate_crew.py --crew-size 8 --seed 42 --output-dir outputs/run1 \
  --run-id run-smoke-001 --created-at 2026-11-01T00:00:00+00:00

# 2. Score the generated records
python score_crew.py --input outputs/run1/crew_observations.jsonl --output-dir outputs/run1

# 3. Run the adaptive-vs-fixed evaluation (will report structured blockers today)
python evaluate_policies.py --observations outputs/run1/crew_observations.jsonl \
  --ground-truth outputs/run1/ground_truth.jsonl --output-dir outputs/run1/eval

# 4. Validate an output record against the exported schema
# (jsonschema is validation tooling, not a backend runtime dependency - any
#  JSON Schema Draft 2020-12 validator in your own stack works identically)
python -c "
import json, jsonschema
schema = json.load(open('../handoff/frontend/schema/astronaut_day_observation.schema.json'))
record = json.loads(open('outputs/run1/crew_observations.jsonl').readline())
jsonschema.validate(record, schema)
print('valid')
"

# 5. Run the full backend test suite
python -m pytest -q
```

Expected result as of this handoff: step 3 prints `Evaluation BLOCKED` and writes
`evaluation_blockers.json` (no CSV/PNG — this is correct, not a failure); step 5
prints `184 passed`.
