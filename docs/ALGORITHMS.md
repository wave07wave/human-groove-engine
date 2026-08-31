# Algorithm map

The pipeline is:

1. Intent and preset resolve to target DNA.
2. Meter grouping produces metric gravity and a virtual beat map.
   The pattern's exact PPQ-dividing subdivision grid may be binary or triplet-based.
3. Phrase grammar and a tension contour are selected from hierarchical seed streams.
4. Closed hat and low-end anchors establish a pulse carrier.
5. Kick, bass, percussion, anticipation, omission, ghosts and recovery events add controlled challenge.
6. Velocity and duration derive from role, metric gravity, instrument identity and phrase tension.
   In learned mode, velocity is blended toward the performance model's conditional target while ghosts
   retain their role-specific soft range.
7. Swing becomes structural tick displacement. In learned mode, style, tempo, instrument, metric
   position and phrase phase select a performance distribution. Simultaneous instruments share a seeded
   timing/velocity latent before receiving instrument residuals. Its output is blended with the rule
   pocket and capped at ±25 ms; rule-only mode remains available.
8. Measurement functions derive DNA from the event pattern.
9. The full candidate pool is ranked symbolically; a fitness/diversity shortlist is rendered through a
   deterministic versioned reference synth. Waveform energy measures low-end overlap, same-band attack
   competition, onset clarity and headroom.
10. The virtual listener estimates surprise, beat retention, recovery, movement, boredom, confusion and
   irritation.
11. Intent fidelity, listener response, learned personal preference and reference-render quality form a
    Pareto frontier; a final quality/diversity pass selects four useful alternatives.

Measured syncopation rewards accented weak positions, explicit violation/anticipation roles and strong
position omissions. Interlock evaluates kick/bass locking plus percussion complementarity. Repetition
compares each bar with its best earlier match, so a returning ABAB motif is recognized even when adjacent
bars differ. Variation compares later bars to the initial motif, so the two are not forced to be inverses.
Omission measures absent non-downbeat Kick anchors, and phrase development measures the energy arch
across bars rather than copying the requested control value.

Partial regeneration generates a fresh deterministic pattern in a new seed namespace, then replaces
only selected instrument/bar regions. Event, instrument and bar locks are filtered before replacement.
The pattern metadata retains its style pocket through this operation.

## Learned Performance Model

The offline trainer reads only `beat`, `4-4` rows from the official Groove MIDI Dataset. Notes are
mapped to the engine's kick, snare, closed/open hat and percussion lanes, quantized to the nearest
sixteenth solely to measure performed residuals, and separated by the dataset's prescribed split.
Robust, centered additive effects model metric position, tempo band and four-bar phrase phase. A
leave-one-instrument-out simultaneous-hit residual estimates shared timing and velocity scale and each
instrument's learned loading. The symbolic Bass lane uses a documented Kick-derived proxy because GMD
contains drums, not pitched Bass.

The runtime never reads training MIDI. It validates a small versioned JSON artifact, derives every
sample from the stable hierarchical seed namespace and records the active model ID/version in Pattern
metadata. Missing, malformed and unsupported artifacts resolve to the deterministic rule pocket.

## Reference Render Analysis

Render profiles define oscillator family, center frequency, attack, decay, gain, transient/noise mix,
frequency band and low-end contribution for all supported lanes. The renderer maps canonical performed
time into waveform samples and maintains a full mix, per-band energy and separate Kick/Bass low-energy
stems. Low-end collision is normalized overlapping stem energy. Transient masking compares each event's
attack-window energy with competing energy in the same broad frequency band. Onset clarity is the
inverse of weighted masking, while headroom derives from the reference mix peak. Its velocity gain uses
the same `velocity^1.25` response as recorded browser drums, keeping candidate scoring aligned with the
audible dynamic hierarchy while remaining a synth-based proxy.

For bounded long-form cost, at most eight bars are chosen at even phrase intervals and each is rendered
with an isolated decay tail. Preview mode reference-renders six shortlisted candidates; high-quality
mode renders twelve. These values do not change `GrooveAnalysis.fitness`; the optimizer consumes
`render_quality` as a separate objective and a small final-selection term.

For Joint generation, the renderer excludes the Groove sketch Bass lane and synthesizes the selected
Human Bass Engine notes at their actual MIDI pitches. Kick/Bass collision and onset clarity are returned
on each requested Joint candidate. When explicitly enabled by the client, reference quality contributes
8 percent to Joint fitness; structural interaction, Bass preference and change cost remain dominant.

## Reference Inputs and Intent Transformation

Tap analysis uses inter-tap intervals rather than wall-clock origin. A 55 percent outlier neighborhood
retains the central pulse, while stable alternating interval classes estimate long/short feel without
counting that alternation as random timing error. The result adjusts tempo, pulse stability,
microtiming and swing with a confidence-weighted blend.

MIDI reference analysis decodes a bounded in-memory payload, merges tracks into absolute source ticks,
converts them to canonical PPQ 960, quantizes to the selected sixteenth grid only for structural
measurement and retains the residual in microseconds. Drum pitches map to supported lanes; other notes
become percussion. The resulting temporary Pattern passes through the normal event-derived DNA
measurement and is discarded after producing a suggested Intent.

Language transformation is a deterministic matched-rule system, not an opaque quality prompt. Rules
apply bounded deltas to named DNA dimensions and may suggest a style/movement target. Responses contain
an explicit change list. No recognized rule means no mutation.

Custom phrase energy control points are linearly interpolated to the requested bar count. Per-bar energy
modulates performed velocity and bounded probabilities for ornaments, weak Kick events, percussion and
transitions while leaving the master seed contract intact.

## Groove Preference Learning

Each score-hidden A/B decision stores all 21 measured Groove DNA features, exact display order, a random
comparison ID and decision time. The server re-analyzes both submitted Patterns instead of trusting
possibly stale client analysis. Comparison IDs are unique and idempotent, so double-clicks and network
retries cannot create additional evidence. A tie is a valid logistic target of 0.5 but does not create a
fictitious selected feature vector or increase decisive evidence.

Both candidates must carry the same style. The stored row uses that style as its profile scope, and
generation requests only the profile matching their requested preset. An unscoped summary remains an
aggregate compatibility/readout path; it is not used for candidate ranking. Legacy rows are classified
from their generation payloads when possible and otherwise remain outside every scoped generator.

A regularized online pairwise logistic model learns directional feature weights, while unique selected
vectors produce preferred ranges and uncertainty. A range receives ranking evidence only when selected
candidates were consistently closer to its centre than rejected candidates; contradictory comparisons
cancel instead of creating false confidence. Repeated copies of the same feature contrast receive
diminishing evidence through `sqrt(n)` effective counting.

Personal scoring combines the directional utility with a smooth distance from the three strongest
evidence-backed ranges. The range mixture grows with `evidence × (1 − uncertainty)` up to 50 percent of
the personal score, so it can learn a middle optimum such as moderate density but stays neutral with one
uncertain observation. Personal weight is separately gated by overall learning confidence and reaches
its 80-percent ceiling only after 25 effective decisive comparisons. Groove and Bass use the same scoring
rule. The profile participates in later candidate ranking but never alters hard locks, the quantized
pattern contract or the requested intent. Four candidates produce six unique pairs, ordered by combined
event/feature distance for the cold start. After each answer, the remaining pairs are re-ranked by 45
percent audible distance, 35 percent unresolved-feature contrast and 20 percent model-boundary
information. Feature knowledge is the stronger of range reliability and confidence-scaled directional
weight. The current pair remains frozen, completed pair keys are excluded and score ties resolve by a
stable key. The UI explains the selection category, requires both auditions, randomizes presentation
order and never shows the internal information or preference scores.

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

Each score-hidden Bass decision stores candidate IDs, exact randomized display order, a unique comparison
ID, decision time and ten normalized Bass features. The server first recomputes analysis from events. An
exact retry is a no-op, conflicting comparison-ID reuse is rejected, and a tie is a logistic target of
0.5 without a selected-range vector or decisive evidence.

An online pairwise logistic regression learns `P(A>B)=sigmoid(w·(xA-xB))` with L2 regularization. Unique
selected vectors produce preferred ranges, but the shared Groove/Bass range scorer uses one only when
winners were consistently closer than losers. Repeated copies of the same absolute feature contrast add
only `sqrt(n)` effective evidence. Personal weight is `0.8 * min(1, effective/25)`, so ties, uncertain
ranges and repetitive feedback cannot overrule the generic model.

The candidates must share the same metadata preset, which becomes the stored profile scope. Standalone
and joint generation request only the active preset's profile before ranking and diversity selection.
The browser uses the shared adaptive scheduler for all six unique pairs from four candidates, with Bass
event/pitch/feature distance as its audible term. It re-ranks unused pairs after every answer, randomizes
presentation, requires both auditions and uses common Kick/chord context when available.

## Preference-guided candidate search

Candidate ranking alone can choose only among sounds the constructive generator already produced. After
at least one comparison and 20-percent learning confidence, generation therefore creates a private guided
Intent beside the original Intent. For each supported feature, range reliability is
`evidence × (1 − uncertainty)` and directional relevance is the absolute learned weight normalized by the
largest absolute weight. A reliable range is used when its signal is at least half the directional signal;
otherwise the weight direction supplies a low/high target. The private target moves by at most
`0.35 × confidence × feature signal`.

Even candidate indices use the original Intent and odd indices use the guided Intent, keeping half of the
search as a deterministic baseline. After construction, every Pattern restores the original user Intent,
rebuilds analysis and—on Bass—decision traces against that Intent. Metadata records only whether guidance
was used, its maximum blend and the contributing preference features. This separates search proposals
from the public request and preserves honest intent-loss measurement.

All 21 Groove DNA features have direct constructive targets. Bass maps syncopation, density, silence,
root usage, chromatic tolerance, pitch motion, timing and duration. Aggregate Kick relationship and
register preference remain ranking-only because they do not correspond honestly to one target. When
chromatic notes are disabled, chromatic preference guidance is disabled before target construction.

## Meter-aware rhythmic call and response

Independent per-instrument probability can create valid events without making them feel like one rhythmic
sentence. Each motif bar therefore receives three deterministic weak-grid landmarks: a Kick call, a
closed-hat answer and a Percussion turnaround. The landmarks are selected from the active meter's actual
subdivision grid, so they remain valid in binary, triplet, compound and odd meters instead of importing a
hidden 4/4-sixteenth assumption.

The same motif label receives the same figure. Syncopation and movement open the offbeat Kick/hat pair;
variation, surprise, interlock and phrase tension open the turnaround. Existing pulse anchors, locks and
recovery remain higher-priority constraints. This gives expressive settings a repeatable hook with a
controlled reply, while restrained settings retain the original sparse carrier.

## Genre rhythm vocabulary

The named built-in styles add arrangement landmarks in addition to their target DNA and pocket timing.
House forces a Kick on every quarter-note beat and reinforces offbeat hats. Rock reinforces an eighth-note
hat spine with low-end anchors on beats one and three. Hip Hop uses a sparse recurring Kick signature and
a probabilistic eighth-note hat layer; its pocket remains later and looser than the forward styles. Funk
continues to use its high interlock, syncopation and ghost-note Intent with its dedicated pocket.

The language profile is active only for recognized built-in names and only in quarter-note meters. Other
meters retain the meter-aware general generator, and user-defined styles receive no unrequested genre
template. Style landmarks are applied after controlled omission, so a House or Rock anchor cannot be
silently removed by a soft variation control.

## Blind performance evaluation

Blind evaluation generates candidate index zero twice from the same request: once with the bundled
learned-performance model and once with the rule pocket. Quantized instrument positions remain identical,
while performed offsets and velocities may differ. System randomness assigns conditions to left and
right. The response removes analysis, replaces performance metadata with `blind`, and uses position-only
identifiers until the listener submits one response.

Decisive learned wins use a two-sided 95 percent Wilson binomial interval; ties remain visible but are
excluded from the win-rate denominator. A six-trial block uses five distinct seeds and silently repeats
the first stimulus in trial six. A canonical stimulus hash links the repeat without encoding its left/right
condition. Consistency compares the selected performance variant across the pair.

The generation request and participant group are frozen for the complete block. A second configuration
fingerprint excludes only the planned seed variation; the server rejects changed settings, repeated
stimuli in trials one through five, a missing first trial or a final trial that is not the anchor repeat.
Saved-choice metadata must match the actual answer.

Producers, drummers and general listeners each require 20 complete blocks. Evidence for the learned model
requires every declared group's lower bound to exceed 0.5. This conservative application gate does not
establish universal superiority.

## Technical engine-quality audit

Control response is a fixed-seed intervention test, not a correlation against Intent. For each primary
control, all other targets remain at defaults while the tested target changes from 0.2 to 0.8. The mean
of its measured DNA across 32 seeds must rise by 0.01. This catches disconnected controls while allowing
individual stochastic candidates to vary.

Structural variation interpolates a motif-stable random stream with a bar-specific stream. Pulse,
movement, ambiguity and surprise then influence stable carriers, anchors, weak violations, ornaments,
percussion and transitions. Candidate diversity continues to use event/role Jaccard distance plus
measured-DNA distance. Audit latency uses rule performance and disables reference rendering to isolate
the symbolic generator and selector.

## Browser hi-hat sample playback

Closed and open hats each use two unpitched CC0 recordings mapped to C4 in independent Tone Samplers.
Mapping and triggering at the source key preserves recorded pitch. A stable FNV-1a hash of `event_id`
selects the take, so repeated playback is identical while adjacent events can use genuinely different
recordings; no random pitch modulation is applied. Velocity controls sampler gain; profile-specific
high-pass filtering, hold duration and release shape Tight/Warm behavior. A fixed per-take trim offsets
source-recording loudness differences without normalizing away their natural transients. A tracked open tail calls
`releaseAll` on every open-hat take when another open or a closed event arrives, implementing the choke
group without stopping closed hits that are already decaying. Playback waits for all local buffers before
the Transport begins.

## Browser drum-kit signal chain

Kick and Snare each use two CC0 acoustic takes from one recorded Tama Starclassic kit. The same stable
event-ID hash used by the hi-hat selects among takes eligible for the event velocity, and Samplers trigger
only at their source key. Kick's softer take covers velocity 0–0.78, its stronger take covers 0.68–1,
and the overlap uses the stable hash; this avoids a hard switch while preventing very soft events from
using the strongest transient. Snare and Percussion takes span the full range and continue to round-robin.
Normalized Pattern velocity becomes gain through `velocity^1.25`, preserving 0 and 1 exactly while
giving ghost and secondary notes more headroom below anchors. The stronger first Kick take has a fixed
-4.5 dB trim to align peaks before Pattern velocity is applied. A
profile-specific low-pass shapes Kick and a low-cut removes Snare rumble without replacing their recorded
transients. Percussion events are generated only as short weak-beat decorations, so they map to two
short studio-recorded wooden Agogô/block strikes selected by the same event-ID hash. A profile-specific
low-cut and duration shape these recordings without pitch shifting. These voices and the hi-hat feed a shared gain stage, compressor
and -1 dB limiter. In Groove-plus-Bass playback, Bass feeds the same dynamics chain so coincident low-end
events cannot bypass peak protection. This processing changes preview sound only and never feeds back
into Pattern timing, velocity or analysis.

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
