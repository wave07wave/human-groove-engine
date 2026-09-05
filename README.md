# Human Groove Engine

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/wave07wave/human-groove-engine)

Human Groove Engine is a working rhythm generator built around stable pulse, controlled prediction
violations and recovery. It generates four deterministic candidates, measures the resulting groove DNA,
estimates a virtual listener response, previews the canonical timing in the browser and exports Type 1
MIDI at PPQ 960.

The repository now also contains the first independently usable **Human Bass Engine** implementation,
designed around the shared Music Core contracts and ready to consume Groove Engine context without
depending on Groove generator internals.

The **Human Keys Engine** adds deterministic, original keyboard accompaniment with independent
Earl Van Dyke-, Joe Hunter- and Johnny Griffith-inspired performance-language controls and a
three-way blend. It uses generated voicings and the existing synthesized preview only; no source
recording or transcribed phrase is bundled.

## Included MVP

- 1–64 bars; 4/4, 3/4, 5/4, 5/8, 6/8 and 12/8
- Eighth, eighth-triplet, sixteenth, sixteenth-triplet and thirty-second grids when the
  selected subdivision fits the meter exactly
- Six instrument lanes: kick, snare, closed/open hat, percussion and bass
- Ten intent presets, eight fast controls and all 21 Groove DNA targets grouped in the detailed editor
- Style-conditioned instrument pockets that preserve the quantized score
- Offline-learned, correlated human timing and velocity from 324,852 performed drum hits, with
  deterministic rule fallback and an explicit comparison mode
- Versioned Studio Tight/Warm Pocket reference sounds with waveform-derived low-end collision,
  transient masking, onset clarity and headroom analysis
- Tap tempo/feel capture, in-memory MIDI reference analysis, editable phrase energy and explainable
  Japanese/English musical-direction transforms
- Hierarchical SHA-256 seed derivation with NumPy PCG64DXSM
- Pattern-derived measured DNA and listener confidence/caveat
- Four fitness-and-diversity candidates
- Unified Tone.js drum kit with velocity-aware deterministic multi-take CC0 Kick, Snare, Hi-hat and wooden Percussion, choke behavior and a protected mix bus
- User-selectable Tight / clear and Warm / soft drum sounds in both easy and detailed workflows
- Step editing, velocity/duration/timing editing and event/instrument locks
- Selected instrument/bar regeneration with invariant non-selected regions
- 20-operation undo/redo history for pattern operations
- Type 1 MIDI export with tempo, time signature, provenance and nonnegative deltas
- SQLite generation, preset and A/B preference persistence
- Score-hidden Groove taste training with ties, idempotent answers, all-21-DNA learning and effective-evidence confidence
- Evidence-backed Groove/Bass preference ranking that learns both directions and preferred middle ranges
- Confidence-limited preference-guided candidate search mixed with unchanged baseline candidates
- Meter-aware call-and-response figures that strengthen offbeat hooks and phrase turnarounds
- Genre rhythm vocabularies for Funk, Hip Hop, House and Rock, alongside neutral custom styles
- Style-separated Groove/Bass preference profiles with legacy-data migration
- Detroit Soul keyboard styles and blend controls in both easy and detailed workflows
- Groove/Bass-aware keyboard phrasing, four candidates, partial regeneration, history and MIDI export
- Adaptive score-hidden Groove/Bass pair scheduling, contextual audition, ties and safe retries
- Consent-gated six-trial blind listening blocks with anchor-retest consistency and group-separated intervals
- Version-bound 21-control response, diversity, determinism and latency quality audit
- Versioned `/api/v1` FastAPI API and OpenAPI-generated TypeScript workflow

## Setup

Python 3.12 or 3.13 is required. From this directory:

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

Run the version-bound engine quality gates with:

```bash
cd backend
../.venv312/bin/python scripts/audit_engine_quality.py
```

Use `--write` only after an intentional engine change has been reviewed; the API rejects a report from
another engine version.

Golden JSON stores target DNA, measured DNA, listener analysis, seed and its paired MIDI filename.

The bundled performance artifact can be reproduced after extracting the official MIDI-only Groove
MIDI Dataset:

```bash
cd backend
../.venv312/bin/python -m scripts.train_performance_model \
  /path/to/groove app/engine/models/gmd-performance-v1.json
```

The raw dataset is not part of this repository. Its attribution, license, source archive checksum and
held-out validation results are recorded in the artifact and in `THIRD_PARTY_NOTICES.md`.

## API

- `POST /api/v1/generate`
- `POST /api/v1/evaluate`
- `POST /api/v1/mutate`
- `POST /api/v1/export-midi`
- `GET /api/v1/preferences?style={style}` and `POST /api/v1/preferences`
- `POST /api/v1/evaluation/sessions`
- `POST /api/v1/evaluation/responses`
- `GET /api/v1/evaluation/summary`
- `GET /api/v1/quality/audit`
- `GET|POST /api/v1/presets`
- `POST /api/v1/reference/taps`
- `POST /api/v1/reference/midi`
- `POST /api/v1/intent/transform`
- `GET /api/v1/capabilities`

Bass endpoints:

- `POST /api/v1/bass/generate`
- `POST /api/v1/bass/evaluate`
- `POST /api/v1/bass/refine`
- `POST /api/v1/bass/mutate`
- `POST /api/v1/bass/export-midi`
- `GET /api/v1/bass/preferences?preset={preset}` and `POST /api/v1/bass/preferences`
- `GET|POST /api/v1/bass/presets`
- `GET|POST /api/v1/bass/patterns`
- `GET /api/v1/bass/history/generations`
- `GET /api/v1/bass/history/generation-records/{generation_id}`
- `GET /api/v1/bass/history/preferences`
- `POST /api/v1/bass/exchange/{pattern,intent,preset}/{export,import}`
- `GET /api/v1/bass/capabilities`

Keyboard endpoints:

- `POST /api/v1/keyboard/generate`
- `POST /api/v1/keyboard/evaluate`
- `POST /api/v1/keyboard/mutate`
- `POST /api/v1/keyboard/export-midi`
- `GET|POST /api/v1/keyboard/patterns`
- `GET /api/v1/keyboard/history/generations`
- `GET /api/v1/keyboard/history/generation-records/{generation_id}`
- `POST /api/v1/keyboard/exchange/pattern/{export,import}`
- `GET /api/v1/keyboard/capabilities`

Bass generation supports chord progressions, key/mode and no-chord input, 1–64 bars, 4/4, 3/4, 6/8
and 12/8 meter-aware behavior, four deterministic/diverse candidates, directed approaches, register and
voice-leading constraints, composed silence, kick lock/complement/answer context, measured Bass DNA,
field-specific regeneration, refine and Type 1 MIDI export.

Use the `GROOVE / BASS / KEYS` switch in the browser to open each detailed workspace. The Bass view
includes a structured
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
Generation History is also browsable: each retained row has its own generation ID and can be loaded back
into the editor through `GET /api/v1/bass/history/generation-records/{generation_id}` without replacing
the saved Pattern library. The legacy latest-by-Pattern-ID endpoint remains compatible.

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
the Interaction trace shows Joint fitness, complexity fit and charged change cost.
For CO-CREATE, the shared budget follows an explicit establish → develop → peak → recover contour
in four-bar phrases; the trace lists every applied joint change, including its target and Tick movement.

The Groove taste trainer hides proxy scores, requires both auditions and accepts ties. It starts with an
audibly distinct pair, then re-ranks every unused pair after each answer using unresolved feature contrast
and the current preference boundary. The server re-analyzes each pair, ignores exact retries through a
unique comparison ID and learns across all 21 Groove DNA fields. The panel separates raw from effective
comparisons and shows confidence, the next-generation personal blend and the strength of each evidence-
backed preferred range.

The Bass taste trainer uses the same adaptive unused-pair scheduling across all six unique pairs from four
candidates, randomizes position, requires both auditions and accepts ties. It compares with common Kick
and chord context when available, then reports raw/effective answers, confidence, next-generation blend
and evidence-backed preferred ranges. Groove styles and Bass behaviour presets learn separate profiles;
standalone and joint Bass generation only use the active preset's evidence.

Once a style- or preset-specific profile reaches 20-percent learning confidence, half of the internal
candidate pool explores gently shifted targets while the other half keeps the requested Intent exactly.
The shift is capped at 35 percent per feature and prefers an evidence-backed range centre over an extreme
direction. Generated Patterns always retain and are evaluated against the user's original Intent; candidate
cards mark the exploratory results as `好み探索`. Bass chromatic prohibition remains a hard constraint,
and unsupported register/Kick-relationship preferences affect ranking only.

Groove generation also gives each phrase motif a meter-aware three-part rhythmic figure: an offbeat call,
an answering hi-hat position and a turnaround. These figures are reused when a motif returns, while higher
syncopation, movement, variation and surprise make them more audible. They work on binary, triplet and
odd-meter grids without assuming a 4/4 sixteenth-note pattern.

Built-in styles now also shape arrangement grammar. House establishes a four-on-the-floor Kick with
offbeat hats; Rock holds a steady eighth-note hat spine and strong low-end anchors; Hip Hop leaves a
repeated, laid-back Kick signature with more space; Funk retains its denser syncopated/ghost-note setup.
This structural vocabulary is applied only to the named built-ins—saved custom styles remain neutral and
fully controlled by their Intent.

FastAPI/Pydantic is the schema source of truth. With the backend running, refresh generated frontend
types via `npm run generate:types` in `frontend/`.

## Known limitations

- The virtual listener is an explainable heuristic, not a scientific pleasure or body-response meter.
- Blind evaluation is anonymous application-level evidence, not a universal coolness score.
- Sound-aware metrics come from the built-in deterministic reference synth, not uploaded, microphone or
  exported audio. They help compare candidates under one controlled sound and are not mastering advice.
- MIDI reference files are analyzed transiently and are not stored. General audio groove transfer is
  not implemented; language control recognizes a documented bounded vocabulary rather than arbitrary
  prose.
- Browser preview uses bundled CC0 acoustic Kick, Snare, Hi-hat and wooden Percussion recordings. Bass
  and optional chord/click context remain synthesized; the backend reference scorer is also a controlled
  synth proxy rather than analysis of those recordings.
- The public demo's server-side Bass/Keys saved libraries and generation history are anonymous shared
  storage, not private user accounts. Render's temporary database can also reset on a restart or deploy.
- Preference learning is deliberately local and small-data; profiles are not synced between devices.
- Adaptive comparison order is an explainable sample-efficiency heuristic, not a guarantee that every
  listener's most informative question is always selected.
- Preference-guided search is a bounded local heuristic, not proof of an aesthetic optimum. It is inactive
  below 20-percent confidence and always competes with unchanged baseline candidates.
- Preview optimization uses a deterministic pool/diversity pass. Longer evolutionary search is reserved
  for a future high-quality engine iteration.
- Audio analysis, groove transfer, realtime MIDI, polyrhythm, VST/AU and cloud features are deliberately
  outside the MVP and hidden through capabilities.

See [design decisions](docs/DECISIONS.md) and [algorithm map](docs/ALGORITHMS.md).
The staged HGE/HBE rollout and acceptance gates are documented in the
[Human Groove Engine integration plan](docs/HUMAN_GROOVE_ENGINE_INTEGRATION_PLAN.md).
