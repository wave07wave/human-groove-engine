# Human Groove Engine

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/wave07wave/human-groove-engine)

Human Groove Engine is a working rhythm generator built around stable pulse, controlled prediction
violations and recovery. It generates four deterministic candidates, measures the resulting groove DNA,
estimates a virtual listener response, previews the canonical timing in the browser and exports Type 1
MIDI at PPQ 960.

The repository now also contains the first independently usable **Human Bass Engine** implementation,
designed around the shared Music Core contracts and ready to consume Groove Engine context without
depending on Groove generator internals.

## Included MVP

- 1–64 bars; 4/4, 3/4, 5/4, 5/8, 6/8 and 12/8
- Six instrument lanes: kick, snare, closed/open hat, percussion and bass
- Ten intent presets and target controls without a misleading “Groove” input knob
- Hierarchical SHA-256 seed derivation with NumPy PCG64DXSM
- Pattern-derived measured DNA and listener confidence/caveat
- Four fitness-and-diversity candidates
- Tone.js preview using backend timing without duplicate swing/humanization
- Step editing, velocity/duration/timing editing and event/instrument locks
- Selected instrument/bar regeneration with invariant non-selected regions
- 20-operation undo/redo history for pattern operations
- Type 1 MIDI export with tempo, time signature, provenance and nonnegative deltas
- SQLite generation, preset and A/B preference persistence
- Versioned `/api/v1` FastAPI API and OpenAPI-generated TypeScript workflow

## Setup

Python 3.12 or newer is required. From this directory:

```bash
/path/to/python3.12 -m venv .venv312
.venv312/bin/pip install -r backend/requirements.lock
cd frontend && npm install && cd ..
```

The current workspace already has these dependencies installed. Start both services with:

```bash
./start.sh
```

Then open `http://127.0.0.1:5173`. The API and interactive OpenAPI schema are available at
`http://127.0.0.1:8000/docs`.

## Web deployment

`Dockerfile` packages the React workspace and FastAPI API as one Web service. This keeps the browser
and API on the same origin, so the same HTTPS URL works on Macs, iPhones and iPads without an API URL
or CORS setting in the client. `render.yaml` selects Render's free Web Service plan. The free plan uses
an ephemeral SQLite database, so saved Patterns, Presets and preference history can reset whenever the
service restarts or redeploys; exported JSON and MIDI files remain available on the user's device.

To publish, connect this repository to a Docker-compatible host that supports `render.yaml` blueprints
or build the root `Dockerfile`. For durable server-side history, upgrade to storage that survives
restarts and set `HGE_DATABASE_PATH` to that mounted volume. The host must route its public `PORT` to
the container. After deployment, open the service URL on any device.

## Validation

```bash
cd backend
../.venv312/bin/pytest -q
../.venv312/bin/ruff check app tests

cd ../frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Regenerate the six required eight-bar, four-candidate golden sets with:

```bash
cd backend
../.venv312/bin/python scripts/generate_golden.py
../.venv312/bin/python scripts/benchmark_interaction.py --bars 8 --candidates 4
```

Golden JSON stores target DNA, measured DNA, listener analysis, seed and its paired MIDI filename.

## API

- `POST /api/v1/generate`
- `POST /api/v1/evaluate`
- `POST /api/v1/mutate`
- `POST /api/v1/export-midi`
- `GET|POST /api/v1/preferences`
- `GET|POST /api/v1/presets`
- `GET /api/v1/capabilities`

Bass endpoints:

- `POST /api/v1/bass/generate`
- `POST /api/v1/bass/evaluate`
- `POST /api/v1/bass/refine`
- `POST /api/v1/bass/mutate`
- `POST /api/v1/bass/export-midi`
- `GET|POST /api/v1/bass/preferences`
- `GET|POST /api/v1/bass/presets`
- `GET|POST /api/v1/bass/patterns`
- `GET /api/v1/bass/history/generations`
- `GET /api/v1/bass/history/preferences`
- `POST /api/v1/bass/exchange/{pattern,intent,preset}/{export,import}`
- `GET /api/v1/bass/capabilities`

Bass generation supports chord progressions, key/mode and no-chord input, 1–64 bars, 4/4, 3/4, 6/8
and 12/8 meter-aware behavior, four deterministic/diverse candidates, directed approaches, register and
voice-leading constraints, composed silence, kick lock/complement/answer context, measured Bass DNA,
field-specific regeneration, refine and Type 1 MIDI export.

Use the `GROOVE / BASS` switch in the browser to open the Bass workspace. It includes a structured
Harmony editor for Root, Quality, Duration and optional Slash Bass, a repeating bar-timeline preview,
Key/Mode controls, behaviour presets, ten macro controls, A/B/C/D candidates, a horizontally scalable
Piano Roll with functional labels, Kick overlay, optional Structural Preview, per-note grid-tick/pitch/
duration/velocity/timing, structural-offset and articulation editing and locks, Undo/Redo, partial regeneration, refine and MIDI download.
Voice Policy can be selected per generation (monophonic retrigger, monophonic legato or overlap), and is
restored when loading a saved or historical pattern. MIDI export exposes a 1–16 channel selector.
Note edits automatically refresh Atomic Features, Bass DNA, Listener analysis and the generation trace
after a short debounce. Pitch, timing, duration, velocity and articulation each have an independent lock.
Partial regeneration also accepts request-level Preserve Options for rhythm, pitch, duration, timing,
motif identity, Kick relationship and register shape; these apply only to the selected regeneration.
Pattern-level Intent Locks persist with saved and exchanged Patterns: Rhythm feel, Register and Kick
relationship remain protected through subsequent regeneration and refine operations.
The structured Harmony editor stays synchronized with the original chord-progression text field, so
either representation can be used without changing the backend request contract.
Register low/center/high and maximum-leap controls now feed generation directly. Current Intent can be
saved as a named user preset. Patterns can be stored in the local library, loaded back into history and
exchanged as schema-versioned `.hbe.json` files.
Generation History is also browsable: each retained generation can be loaded back into the editor through
`GET /api/v1/bass/history/generations/{pattern_id}` without replacing the saved Pattern library.

Clicking a Bass Note shows its musical reason. `TRACE` opens the full debug explanation for why that
onset, pitch, duration, octave and articulation were chosen, including normalized decision factors and
any directed approach target. `POST /api/v1/bass/explain/{event_id}` exposes the same trace to clients.

After generating or selecting a Groove candidate, switch to Bass and choose `LINK CURRENT GROOVE`.
The adapter transfers canonical tempo, meter, phrase boundaries, metric gravity, tension, Groove DNA
and performed Kick events through `GrooveContext`; both engine workspaces keep their editing histories.
Preview modes are Bass Only, Bass + Click, Bass + Kick, Bass + Chords and Bass + Kick + Chords. These
context tracks do not add swing or humanization to the Backend Bass timing.

The Bass workspace exposes all three integration modes across the shared 1–64 bar contract. Groove
events carry generated/user-edited/regenerated provenance so Interaction Core can protect manual work.
`FOLLOW` fixes drums, `NEGOTIATE` permits at
most one beneficial unlocked Kick onset repair per candidate, and `CO-CREATE` jointly replans only the
unlocked Kick lane with Bass. Shared complexity and Bass-share controls feed the Joint optimizer;
candidate cards and the Interaction trace show Joint fitness, complexity fit and charged change cost.
For CO-CREATE, the shared budget follows an explicit establish → develop → peak → recover contour
in four-bar phrases; the trace lists every applied joint change, including its target and Tick movement.

The A/B panel randomizes candidate position and feeds a regularized pairwise preference model. The
Personal Taste panel shows comparison count, the generic/personal blend and the most certain preferred
feature ranges. Learned preference re-ranks both standalone Bass and joint-generation pools.

FastAPI/Pydantic is the schema source of truth. With the backend running, refresh generated frontend
types via `npm run generate:types` in `frontend/`.

## Known limitations

- The virtual listener is an explainable heuristic, not a scientific pleasure or body-response meter.
- Preview uses synthesized browser instruments; sound design is intentionally minimal, while note
  connection, technique and accent metadata shape release length and preview gain.
- Preference learning is deliberately local and small-data; profiles are not synced between devices.
- Preview optimization uses a deterministic pool/diversity pass. Longer evolutionary search is reserved
  for a future high-quality engine iteration.
- Audio analysis, groove transfer, realtime MIDI, polyrhythm, VST/AU and cloud features are deliberately
  outside the MVP and hidden through capabilities.

See [design decisions](docs/DECISIONS.md) and [algorithm map](docs/ALGORITHMS.md).
The staged HGE/HBE rollout and acceptance gates are documented in the
[Human Groove Engine integration plan](docs/HUMAN_GROOVE_ENGINE_INTEGRATION_PLAN.md).
