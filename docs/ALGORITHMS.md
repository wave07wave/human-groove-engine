# Algorithm map

The pipeline is:

1. Intent and preset resolve to target DNA.
2. Meter grouping produces metric gravity and a virtual beat map.
3. Phrase grammar and a tension contour are selected from hierarchical seed streams.
4. Closed hat and low-end anchors establish a pulse carrier.
5. Kick, bass, percussion, anticipation, omission, ghosts and recovery events add controlled challenge.
6. Velocity and duration derive from role, metric gravity, instrument identity and phrase tension.
7. Swing becomes structural tick displacement. Pocket, phrase contour and small seeded noise become
   microseconds, with a ±25 ms safety limit.
8. Measurement functions derive DNA from the event pattern.
9. The virtual listener estimates surprise, beat retention, recovery, movement, boredom, confusion and
   irritation.
10. Intent fidelity, listener response, coherence and candidate distance select four useful alternatives.

Measured syncopation rewards accented weak positions, explicit violation/anticipation roles and strong
position omissions. Interlock evaluates kick/bass locking plus percussion complementarity. Repetition
uses adjacent-bar Jaccard similarity; variation compares later bars to the initial motif, so the two are
not forced to be inverses.

Partial regeneration generates a fresh deterministic pattern in a new seed namespace, then replaces
only selected instrument/bar regions. Event, instrument and bar locks are filtered before replacement.

## Human Bass Engine

The frontend represents chord progressions as a small editable Harmony Plan. Each item has Root,
Quality, bar Duration and optional Slash Bass. Parsing collapses adjacent identical chord symbols into
one duration-bearing item; serialization expands them back to the backend's bar-delimited chord string.
The bar preview repeats the resulting chord cycle independently of the Bass phrase length. Unsupported
free-text chord syntax remains untouched and simply suspends the structured view, preserving the text
input as the compatibility boundary.

The Bass pipeline is:

1. Parse chord, key/mode, root-guide or explicit no-harmony input into `HarmonyTimeline`.
2. Resolve conflicting soft intent targets while retaining the original target for fidelity analysis.
3. Plan four-bar phrase roles and motif memory independently of the harmony cycle.
4. Score meter-aware onset slots using gravity, density, syncopation and the supplied kick relationship.
5. Compose structural gaps separately so density and active occupancy remain independent.
6. Generate chord/scale candidates across the register and score harmonic function, root preference,
   voice leading, contour, role stability and register suitability.
7. Sample with a variation-controlled softmax rather than taking every maximum.
8. Convert eligible weak/boundary notes into diatonic or chromatic approaches only when a stable target
   event exists; the target stable ID is stored on the approach.
9. Bound unjustified leaps, then derive duration, connection, technique, velocity and layered timing.
10. Validate the pattern, measure atomic features, derive Bass DNA and interaction DNA, run the virtual
    listener, and select a fitness/diversity set.

Partial Bass regeneration uses operation-specific seed namespaces. Pitch-only retains IDs, onsets,
structural timing, microtiming and durations; equivalent invariants apply to the other field operations.
Manual Piano Roll moves edit `grid_tick` while leaving structural and micro timing separate; both canonical
performed-time bounds and the nonnegative model constraint are enforced before the same evaluation/trace pipeline.
The note inspector also edits connection, technique and accent metadata; these edits are marked
`user_edited` and invalidate stale analysis/traces until the debounced evaluator refreshes them.
Structural Preview renders `BassStructuralEvent` spans (phrase breaks, intentional gaps, Kick exposure
and recovery targets) in a dedicated strip below the pitch surface, keeping structural silence visually
distinct from sounding Notes.
Per-field locks are checked before mutation. Request-level Preserve Options add temporary invariants:
Kick-relation preservation fixes performed onsets, motif preservation restores the motif's pitch/rhythm/
duration identity, and register-shape preservation keeps changed pitches on the original side of the
preferred center. Persistent Intent Locks are stored on the Pattern and merge into every mutation and
refine request: Rhythm feel protects grid and microtiming, Register protects the center-side contour,
and Kick relationship protects performed onsets. MIDI is built in absolute time with meta, note-off and
note-on priority, then converted to nonnegative deltas with monophonic retrigger safety.

## Interaction Core

`FOLLOW` adapts the selected Groove candidate to `GrooveContext` and generates Bass without changing
any drum event. `NEGOTIATE` first solves Bass-specific issues on the Bass side; when interaction remains
weak it considers one performed-onset repair on the nearest unlocked Kick, charges a change cost and
keeps the repair only when Joint fitness improves. Instrument locks, event locks and bar locks exclude
Kick edits.

`CO-CREATE` generates deterministic alternative Kick lanes while retaining every non-Kick event. Locked
Kick events and locked bars are copied from the source and excluded from replacement. Bass is generated
against each resulting context. Selection uses Bass fitness, Groove fitness, Interaction DNA, shared
low-end complexity fit and normalized change cost. The entire drum pattern is never regenerated merely
to solve a Kick/Bass interaction problem.

## Bass Preference Learning

Each A/B decision stores candidate IDs, randomized display order, normalized Bass features, selection
and timestamp. An online pairwise logistic regression learns `P(A>B)=sigmoid(w·(xA-xB))` with L2
regularization. Selected absolute feature vectors also produce preferred ranges and uncertainty.

Candidate selection blends generic fitness with the personal score. Personal weight starts at zero and
rises gradually to an 80% ceiling over the first 25 comparisons, so sparse feedback cannot overrule the
generic model. Standalone and joint generation use the same blended Bass score before diversity
selection.

## Persistence and Exchange

SQLite keeps versioned generated patterns, explicitly saved patterns, user presets and pairwise history
as separate records. Pattern loading creates a normal editor-history commit. JSON exchange wraps a
Pattern, Intent or Preset with a discriminating `kind` and exact schema version; incompatible versions
fail validation instead of being silently interpreted. Register bounds, preferred center and maximum
single leap are retained in each saved or exchanged Bass Pattern. Generation History stores the complete
Pattern payload separately from the user library; a latest-by-pattern-id endpoint restores it as a normal
editor load while preserving the original generated metadata and analysis.

## Note Decision Trace

Every generated Note carries a structured trace for onset, pitch, duration, octave and articulation.
The trace references the final performed state: phrase phase, metric gravity, Kick relationship, active
harmony, register-center distance, target Note, duration, velocity and microtiming. Numeric factors are
stored separately from prose for debug inspection. Partial regeneration rebuilds traces and records the
mutation operation; manual frontend edits invalidate the affected trace until evaluation rebuilds it.
