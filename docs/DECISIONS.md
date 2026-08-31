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

`subdivisions_per_quarter` is also canonical. It must divide PPQ 960 and the complete bar without a
remainder. This supports binary and triplet grids without float timing and prevents an incompatible
grid—such as an eighth-triplet grid that cannot close a 5/8 bar—from silently truncating the phrase.

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

Groove preview evaluates 16 candidates and high-quality mode evaluates 64. Selection keeps intent fit,
movement prediction and personal preference as separate objectives before the diversity pass; there is
intentionally no universal “coolness” scalar exposed as ground truth.

## Style-conditioned pocket

Human feel is a coherent relation between instruments, not independent random displacement. Built-in
styles therefore select deterministic per-instrument offsets, residual variation and phrase contour.
The style is stored in pattern metadata, so partial regeneration cannot silently switch pocket.

## Learned performance and fallback

The learned layer changes performed timing and velocity, never the quantized event score. It is a small
statistical artifact rather than a runtime neural dependency: this keeps generation fast, inspectable
and exactly reproducible. A shared latent is keyed by model, candidate, bar and slot so instruments at
the same musical instant move together; instrument-specific residual streams remain independent.

Training uses the Groove MIDI Dataset's prescribed training split only. Validation metrics are stored
in the artifact and are framed as prediction checks, not a universal quality score. The model loader is
fail-closed: absent, malformed, non-finite or schema-incompatible data activates `rule-pocket-v1`.
Patterns record the chosen model ID/version, and partial regeneration retains rule-versus-learned mode.
The raw licensed dataset is never shipped with the application.

## Sound-aware quality boundary

Sound-aware ranking uses deterministic reference synthesis, not symbolic estimates mislabeled as audio
measurement. Profiles are external versioned JSON, validated before use and recorded in Pattern
metadata. Invalid or disabled profiles produce no render analysis rather than fabricated zero scores.
The frontend preview selects corresponding tight/warm envelopes so audition and evaluation point in the
same direction, while the backend remains the canonical measurement implementation.

Symbolic fitness is intentionally unchanged. The full candidate population is first measured and
ranked symbolically; only a diverse shortlist incurs waveform cost. Reference-render quality then joins
the Pareto objectives and contributes 10 percent to final comparison. This prevents one provisional kit
model from becoming a universal definition of groove. `audio_analysis` remains disabled in capabilities;
the separate `reference_render_analysis` flag prevents clients from implying that recorded audio was
inspected.

Joint analysis uses the independent Bass Engine pattern rather than the Groove generator's sketch Bass
lane, matching the actual combined preview. The request flag defaults off for backward-compatible
programmatic workflows; the first-party UI enables it. The resulting audio term is deliberately limited
to 8 percent of Joint fitness.

## Reference-input safety

Tap, MIDI and language inputs produce proposed Intent, not direct hidden edits to an existing Pattern.
This preserves Undo/Redo, locks, partial-regeneration invariants and deterministic seeds. Tap timestamps
must be finite and increasing. MIDI is limited to 2 MB and 20,000 onsets, parsed entirely in memory,
never persisted, and restricted to synchronous Type 0/1 files. Unsupported meters fall back visibly
rather than being guessed silently.

Natural-language control deliberately uses a small inspectable bilingual vocabulary. It does not claim
general language understanding, and an unmatched phrase is a no-op. This is safer and reproducible;
future learned language mapping can replace it only with versioned transformations and evaluation.

Phrase energy belongs to `GrooveIntent`, not measured DNA: it is a requested contour, while the resulting
event variation/density/velocity continue to be measured afterward. Empty curves preserve legacy
automatic behavior, making the schema addition backward-compatible.

## Blind evaluation is not preference learning

Personal A/B choices continue to train the local preference profile. Blind performance evaluations use a
separate table and never affect candidate ranking, preventing the experiment from changing the system it
measures. Sessions require explicit consent, collect no name or contact identifier, accept one response,
and reveal conditions only afterward. Pre-response analysis, model metadata and condition-bearing
identifiers are removed from the public payload.

The release verdict is deliberately conservative and group-specific. Minimum sample size and confidence
intervals are product wording gates, not proof of a universal human response.

Listening trials are grouped by an opaque, block-scoped random ID. It is not a durable participant ID.
The first stimulus is repeated only at the end of a six-trial block, and the UI does not announce the
anchor. Release minimums count complete blocks, not correlated trial rows, to avoid obvious
pseudoreplication. Repeat consistency is reported as a diagnostic and does not silently remove responses.

## Personal taste trials use effective evidence, not click count

The personal Groove trainer is separate from the learned-versus-rule performance study. It hides proxy
scores, requires both candidates to be auditioned, permits a tie and works through every unique pair in
distance-first order. A random comparison ID makes submission idempotent. The backend re-analyzes the
Patterns and rejects reused IDs with conflicting payloads, so client state cannot forge or duplicate
evidence.

Raw response count remains visible, but personal influence is based only on effective decisive evidence.
Repeated feature contrasts contribute `sqrt(n)` rather than `n`; ties shape only the equality boundary.
All 21 public Groove DNA dimensions participate automatically. This deliberately slows confidence growth
when a listener repeats one easy comparison and preserves uncertainty until varied examples exist.

Directional pairwise weights alone can express “more” or “less” but not “around the middle.” Preferred
ranges therefore join the personal score only when the winning candidates are consistently nearer the
range centre than the rejected candidates. Opposing observations cancel; statistical uncertainty further
reduces influence. Ranking uses at most the three strongest ranges and caps their share at half of the
personal score, limiting small-data overfitting while allowing stable middle-value preferences. The same
calculation is shared by Groove, standalone Bass and joint Groove/Bass ranking.

Six-trial performance-study settings are frozen independently. The browser retains the first request and
the database enforces a configuration fingerprint plus the final anchor stimulus, preventing mid-block
control changes from corrupting group evidence.

## Technical audit and perceptual evidence remain separate

The bundled quality audit verifies control direction, diversity, deterministic reproduction and local
latency. It deliberately runs offline and binds its report to the engine version; normal API requests do
not trigger a costly benchmark. Latency is a regression threshold for the recorded runtime, not a device-
independent performance promise. The audit schema fixes `perceptual_quality_claim` to false, so passing
technical gates cannot authorize subjective superiority language.

## Recorded hi-hats replace the procedural prototype

The first browser preview used `square8`; the next prototype used filtered noise plus MetalSynth. Listening
feedback still identified a repeating pitched beep, so all tonal synthesis was removed from the hi-hat.
The production voice uses separate CC0 acoustic recordings and explicit open/closed choke behavior. Files
are local for offline playback. Source, author, license, transformation and SHA-256 are recorded in the
third-party notice; a sample without equivalent provenance must not replace them.

## Recorded take variation is deterministic and unpitched

One closed and one open recording removed the synthetic timbre but repeated the exact same transient on
every event. Each articulation now has two genuine acoustic takes. The stable event identifier chooses a
take through a small deterministic hash, preserving exact replay, export comparison and blind-test
repeatability. We deliberately do not pitch-shift takes: pitch randomization can create the same tonal
warble that the recorded-hat change was intended to remove. Open-hat choke releases all possible open
takes because the currently sounding take may differ from the next one.

## Kick and Snare use one coherent recorded kit

After the hi-hat became fully recorded, the synthesized membrane/noise Kick and Snare no longer matched
its acoustic detail. Both have been replaced by two CC0 takes recorded from the same Tama Starclassic
kit. Using a single kit matters more than maximizing the number of unrelated samples: deterministic
round-robin should vary a drummer's strike, not appear to swap the drum itself. Source-key playback keeps
pitch fixed, Pattern velocity controls performance level, and a documented fixed trim corrects the one
large source peak difference.

## Auxiliary Percussion maps to short wooden strikes

Generator inspection confirmed that the generic Percussion lane is restricted to short, weak-beat
decoration and avoids most Kick/Snare collisions. Two brief CC0 wooden Agogô/block strikes therefore form
a neutral acoustic mapping without implying a conga, shaker or long cymbal performance that the Pattern
does not encode. They share one recording chain, use deterministic take selection and preserve recorded
pitch. If future generation adds explicit percussion techniques, `timbre_variant` should carry that
meaning rather than inferring it from arbitrary timing after generation.

## Velocity selects performance intensity before gain

Pure event-ID round-robin can choose a strong acoustic transient for a soft event. Recorded takes may
therefore declare overlapping normalized velocity ranges. Selection first finds the closest eligible
range, then hashes the event ID only within that set. Kick uses overlapping soft and strong layers;
Snare, Hi-hat and Percussion retain full-range variation because their current pairs are not documented
velocity layers. A monotonic `velocity^1.25` gain curve is shared by every recorded voice. Generated
ghost roles already receive low MIDI velocity in the canonical Pattern, so playback respects that
contract instead of applying a second hidden role classifier. Dedicated ghost samples should be added
only when they are true isolated strikes from a compatible kit, not a roll that changes event semantics.

## Drum sound choice is musical, not an analysis switch

The previous detailed UI called `render_profile` an audio-evaluation setting and exposed `off`. Browser
playback interpreted `off` as Tight, so the visible choice could disagree with what users heard. The UI
now presents only two musical choices: Tight / clear and Warm / soft. The backend-only `off` value remains
available for technical audits and reference workflows but is not a user-facing drum sound. Easy mode no
longer hard-codes Tight. Changing a detailed pattern's drum sound updates its metadata and re-evaluates
the derived render analysis while preserving the symbolic events. Server-derived analysis replaces the
current edit rather than creating a second Undo step.

## Every Groove intent dimension must produce an observed response

The earlier release audit covered only the eight primary knobs, leaving several schema-level controls
present but weakly connected. Engine 0.10 audits all 21 `GrooveDNA` fields at low and high targets over
32 fixed seeds. New schema fields join the audit automatically. Beat salience now separates strong and
weak carrier energy, low-end anchor affects both Kick placement and Bass lock, anticipation creates
explicit anticipations, and hypnotic intent affects phrase grammar as well as structural randomness.
Omission, returning motif repetition and phrase development are measured from observable events. This
is still a directional regression gate, not proof that one setting is aesthetically better.

## Detailed shaping groups all 21 controls by musical purpose

The old advanced tabs changed only their highlighted label and always displayed the same first eight
measurements. They now expose every Groove DNA target in seven musical groups and show the corresponding
target-to-measured response beside each control. The Listener tab is read-only and retains explicit proxy
language. The eight primary controls stay visible for speed; advanced shaping adds precision without
making the quick workflow more technical.

## Async evaluation may replace only the edit that requested it

Groove edits are evaluated asynchronously. A monotonically increasing local sequence now invalidates an
older response whenever a newer edit, generation, candidate selection, regeneration, external Pattern,
Undo or Redo occurs. The server-derived analysis still replaces the current history entry, but a delayed
response can no longer restore an obsolete sound profile or event edit.

## One preview drum kit and one protected output path

Groove-only and mixed preview previously duplicated drum constructors, which allowed sound and cleanup
behavior to drift. A shared kit now owns every drum node and its dynamics chain. Bass also enters that
chain in Groove preview and Groove-plus-Bass preview; the limiter therefore observes the combined peak.
The dynamics are monitoring-safe preview processing, not a mastering model and not part of sound-aware
candidate scoring.

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
Repeated refinements can legitimately reuse a deterministic Pattern ID, so that ID is not a unique
history key. Every retained row now exposes its SQLite generation ID, and the UI loads the exact row
through a record endpoint. This removes duplicate React keys and prevents two visually separate history
entries from both resolving to the newest payload. Loading still commits into the existing editor
history, so users can undo it without conflating it with the saved-library record.

## Piano Roll positioning

Grid Tick is editable independently from microtiming. The UI clamps manual positions to the canonical
pattern range before evaluation, preserving the nonnegative performed-time contract while still allowing
rhythmic Note moves to be analyzed and traced like generated events.

## Preference profiles follow musical context

Preference is conditioned on the generating style, not treated as one universal taste vector. Groove
uses `PatternMetadata.style`; Bass now records `BassPatternMetadata.preset`. A comparison is valid only
when both candidates share that value, and every generation path—including joint generation—queries the
same scope explicitly. The aggregate API view exists for compatibility and inspection, not ranking.

Migration preserves every historical answer. Candidate IDs are resolved against generation payloads at
or before the answer timestamp; matching styles are backfilled, while unresolved rows stay in a legacy
global scope. This is safer than guessing a style from feature values and safer than allowing old mixed
evidence to leak into every new preset.

## Groove and Bass use the same listening-evidence contract

Bass preference used to trust browser analysis, accept only A/B, allow repeated inserts and compare the
same first two candidates. It now follows the Groove contract: score-hidden complete pair scheduling,
both auditions before response, ties, server re-analysis, unique idempotency keys, decision time,
diminishing repeated evidence and confidence-gated influence. Bass retains its own ten-feature model and
contextual preview because its musical question is whether it supports the Kick and harmony, not whether
it is impressive in solo playback. Both engines use the same evidence-and-uncertainty-gated range score,
so Bass can learn a preferred middle value without receiving a stronger or less guarded model than Groove.

## Preference questions adapt without revealing a predicted winner

A fixed distance-first list wastes later answers once the profile has changed. The first question still
uses broad audible contrast; subsequent questions combine audible distance, contrast in features that
remain weakly known and entropy near the current directional decision boundary. Range reliability and
confidence-scaled directional weight reduce exploration only for features with actual evidence.

This is an inspectable scheduling heuristic, not a claim of optimal Bayesian experimental design. The
numeric score and predicted winner remain hidden. The UI shows only whether a pair was chosen for broad
contrast, an uncertain feature or a close preference boundary. The pair being heard never moves after a
response arrives; only unused pair keys are re-ranked, so adaptive ordering cannot duplicate or silently
replace an in-progress comparison.

## Preference may propose search targets but may not rewrite user Intent

Personal ranking cannot recover a desirable region that is absent from the candidate pool, but directly
replacing the user's Intent would make the controls misleading and corrupt intent-loss analysis. The
engine instead alternates unchanged candidates with preference-guided exploratory candidates. Guidance
starts only at 20-percent confidence and moves any target by at most 35 percent, scaled again by feature
evidence. An evidence-backed middle range takes precedence over extrapolating toward zero or one.

The exploratory Intent is never returned. A generated Pattern restores the exact requested Intent before
analysis; Bass also rebuilds public decision traces and original conflict-resolution notes. Metadata and
the candidate card disclose that a candidate came from `好み探索`, including machine-readable strength
and features, without exposing a predicted winner during preference questions.

Groove can map every learned feature directly. Bass deliberately leaves register and aggregate Kick
relationship as ranking-only signals, and never permits a chromatic preference to override
`allow_chromatic_notes=false`. Keeping half the pool unchanged supplies a baseline, prevents learned taste
from narrowing all exploration and makes the method deterministic for a fixed request and profile.
