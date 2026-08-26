# Design decisions

## Canonical timing

Grid time, structural displacement and performance microtiming remain separate. `grid_tick` and
`structural_offset_tick` use PPQ 960; `micro_offset_us` remains in microseconds. Browser preview and
MIDI export both consume the same three fields. Tone.js does not add swing or humanization.

## Meter grouping

Metric gravity is calculated from `MeterDefinition.grouping`, then refined at quarter, eighth and
sixteenth levels. No fixed 16-step gravity array exists. The supplied 4/4 `[2,2]`, 3/4 `[2,2,2]`,
5/4 and 5/8 `[3,2]`, 6/8 `[3,3]` and 12/8 `[3,3,3,3]` interpretations therefore remain
distinct. Although 5/4 and 5/8 share the 3+2 accent shape, their canonical bar and group durations
differ by a factor of two.

## Reproducibility

Every random stream is derived from a master seed plus semantic namespace using SHA-256. NumPy
PCG64DXSM performs sampling. Event identifiers use the same stable derivation, so a complete JSON
pattern is reproducible—not only its note positions.

## Generation and measurement

The generator sees target DNA. Measurement functions only inspect pattern events and meter; they do
not read the target. Intent loss is computed afterward, in the listener/optimizer boundary. This is
the main safeguard against a UI knob being reported back as if it were an observed property.

## Optimizer scope

Preview mode creates a deterministic candidate pool and applies a fitness/diversity selection pass.
High-quality mode expands the pool. This MVP does not implement long-running eight-generation
evolution; the cause-specific mutation boundary and fitness terms are kept separate so it can be
expanded without changing the API or pattern schema.

## Listener language

Listener scores are heuristics. The API carries a caveat and confidence value, while the UI labels the
result as a proxy and explicitly says that it is not physiological measurement.

## Python runtime

The app targets Python 3.12+. The local OS default was Python 3.14, which was newer than the pinned
Pydantic core supported during validation. Setup and `start.sh` therefore use the bundled Python 3.12
runtime explicitly.

## Bass Engine boundary

The Bass Engine lives in `backend/app/bass` and reuses only shared timing, meter and deterministic
seed primitives. It never imports Groove generator internals. Integration crosses the versionable
`GrooveContext` DTO; `groove_context_from_pattern` is the sole adapter from the current Groove model.
This avoids duplicating PPQ, meter gravity or seed derivation while keeping Bass independently testable.
The UI obtains this DTO through `POST /api/v1/bass/context/from-groove`; it never reconstructs a second
beat map in TypeScript. Groove and Bass workspaces stay mounted when switching so their undo histories
and selected candidates survive the handoff.

## Bass harmony and rests

Harmony is stored as a timeline with explicit `NO_CHORD` events. Enharmonic pitch spelling is retained
beside pitch class. Sounding notes and structural silence use distinct models; rests are never encoded as
MIDI notes. Harmony can cycle independently while phrase and motif identities continue over 64 bars.

## Bass optimization scope

Bass generation is constructive: feasibility resolution, phrase-aware rhythm skeleton, harmonic
candidate scoring, softmax sampling, voice-leading bounds, directed approach assignment, register,
duration, articulation, velocity and timing. Candidate selection combines intent-dominant fitness with
feature/rhythm distance. Cause-specific refine and field-specific mutation are implemented without a
global evolutionary pass.

## Target, measurement and listener semantics

`BassIntentDNA`, `AtomicBassFeatures` and `DerivedBassDNA` are separate schemas. Every exposed target has
a generator mapping and an event-derived measurement. Kick metrics are `Not Applicable`, never zero,
when no kick context exists. Listener outputs remain confidence-bearing heuristic proxies.

## Edited-pattern analysis and history

Frontend Note edits invalidate measured analysis and decision traces, then debounce a backend
`evaluate` request. The evaluated Pattern replaces the current history value instead of creating a new
commit: Undo therefore represents a user action, not a server-derived analysis refresh. The selected
Note is always resolved again from the current history Pattern so its Inspector cannot retain stale lock
or trace state after Undo/Redo.

## Event locks and regeneration preservation

Event Locks are durable per-Note constraints. Preserve Options are intentionally request-scoped and do
not mutate Bass Intent or saved Event Locks. `keep_kick_relation` preserves performed onset because the
relationship is timing-derived; `keep_motif` restores the motif-bearing Note's pitch, rhythm and duration;
`keep_register_shape` allows a pitch-class change but prevents crossing the preferred register center.

## Generation History loading

Generation History retains full versioned Pattern payloads independently of explicitly saved Patterns.
The UI exposes a bounded recent list and loads one selected payload through a dedicated ID endpoint;
loading commits into the existing editor history, so users can undo the load without conflating it with
the saved-library record.

## Piano Roll positioning

Grid Tick is editable independently from microtiming. The UI clamps manual positions to the canonical
pattern range before evaluation, preserving the nonnegative performed-time contract while still allowing
rhythmic Note moves to be analyzed and traced like generated events.
