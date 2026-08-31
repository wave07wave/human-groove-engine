# Groove Quality Implementation Plan

## Goal

Make the engine reliably discover a listener's preferred groove without presenting a heuristic score
as an objective definition of musical quality. Generation remains deterministic for the same input,
seed, engine version and preference profile.

## Final plan review

The original improvement proposal needed four constraints before implementation:

1. Quality is multi-objective. Intent fit, movement proxy, personal preference and candidate diversity
   must remain separate during selection.
2. Humanization is a coherent, style-conditioned relationship between instruments. Independent random
   displacement is not a valid pocket model.
3. Pairwise feedback must influence later candidate ranking. Persisting comparisons without consuming
   the learned profile is incomplete.
4. Larger representation changes—triplets, arbitrary subdivisions, audio analysis and realtime MIDI—
   require schema and interaction work and must not be advertised before their acceptance tests pass.

## Implemented in this iteration

- Style-conditioned pocket profiles for all built-in Groove presets.
- Pocket style stored in pattern metadata and preserved by partial regeneration.
- Syncopation measurement based on weak-to-strong hierarchical expectation violations, separated from
  raw density.
- Pattern-frequency prediction surprise instead of a one-way accumulating seen-position set.
- Microtiming irritation based on within-instrument irregularity rather than penalizing all deviation.
- 16 preview candidates and 64 high-quality candidates.
- Pareto filtering across intent fidelity, movement prediction and personal preference, followed by a
  quality/diversity selection pass.
- Regularized pairwise Groove preference learning, preferred ranges, uncertainty and gradual personal
  weighting up to 80 percent.
- Learned Groove preference applied to later generation and exposed in the API and UI.
- Randomized A/B display order and a visible personal-taste summary.

## Acceptance gates

- Identical inputs remain deterministic when the preference profile is held constant.
- Pocket changes affect performed timing but do not silently change the quantized score.
- Partial regeneration retains the pattern's pocket style.
- Selected A/B examples receive a higher learned personal score after repeated comparisons.
- Every exposed measured DNA value remains in the normalized range.
- Existing API, MIDI, lock, meter, Bass and Interaction Core tests continue to pass.
- Frontend tests, lint, typecheck and production build pass.

## Next safe phases

### Phase 2: rhythmic representation — implemented

- The existing `subdivisions_per_quarter` contract now drives generation, analysis, editing, partial
  regeneration, Groove-to-Bass context, Bass generation and MIDI-preserving canonical ticks.
- Supported UI grids are eighth, eighth-triplet, sixteenth, sixteenth-triplet and thirty-second.
- A grid must divide both PPQ 960 and the selected bar exactly; invalid combinations are rejected by
  validation and disabled in the UI instead of truncating the bar.
- Existing patterns remain sixteenth-based by default, so no schema migration is required.

Remaining research item: add meter- and culture-specific rhythm priors as selectable, provenance-aware
knowledge packs.

### Phase 3: learned performance — implemented

- The bundled `gmd-performance-v1` model was trained offline from 324,852 hits in the official Groove
  MIDI Dataset training split. Only 4/4 beat performances were fitted; validation and test rows were
  excluded from fitting.
- Timing and velocity are conditioned on app style, tempo band, instrument, metric position and
  four-bar phrase phase. A shared seeded latent preserves correlated movement between simultaneous
  instruments, followed by an instrument residual.
- The independent validation split contains 39,453 hits. Mean timing MAE improves from 22.04 ms for a
  zero-offset baseline to 20.12 ms; velocity MAE improves from 35.43 for fixed instrument velocities to
  27.93. These are model-fit checks, not claims of perceptual superiority.
- Quantized event placement is invariant between learned and rule modes. The existing ±25 ms safety
  limit, deterministic seed tree, locks and MIDI contract remain unchanged.
- `auto` activates the bundled model and safely falls back to `rule-pocket-v1` when the file is absent,
  malformed or incompatible. The UI also exposes an explicit rule comparison mode.
- Model provenance, dataset license, source URL, archive checksum, training counts and held-out metrics
  are stored with the artifact. The raw dataset is not redistributed.

### Phase 4: sound-aware quality — implemented

- Two validated, versioned reference profiles now cover every Drum lane and the symbolic Bass lane:
  `studio-tight-v1` and `warm-pocket-v1`. The selected profile is stored in Pattern metadata and also
  shapes browser preview synthesis.
- A deterministic 8 kHz reference renderer measures Kick/Bass low-end overlap, same-band transient
  masking, onset clarity and headroom from synthesized waveforms. Phrases longer than eight bars are
  sampled evenly from opening to final bar instead of silently evaluating only the beginning.
- Candidate search is explicitly two-stage: the full 16/64 pool receives symbolic evaluation, then a
  fitness/diversity shortlist of 6/12 candidates receives waveform analysis. Symbolic fitness and
  rendered quality remain separate objectives; rendered quality receives only 10 percent weight in the
  final comparison score.
- Joint Groove/Bass generation replaces the Groove sketch Bass lane with the actual Human Bass Engine
  notes for reference rendering. Its rendered quality contributes 8 percent to Joint fitness and is
  returned beside the structural interaction analysis.
- The API and UI call this a reference-synth simulation. `audio_analysis` remains false because uploaded,
  exported or microphone audio is not being analyzed.
- Determinism, profile validation, path safety, long-form coverage, disable mode, low-end-overlap
  response and selected-candidate completeness have automated acceptance tests.

The randomized blind-listening collection workflow is implemented in Phase 6. The app must not claim
perceptual superiority until sufficient producer, drummer and general-listener results exist.

### Phase 5: new intent inputs — implemented

- Three or more tap timestamps produce a robust median tempo, timing stability and alternating long/short
  feel. Outlier filtering, a 30–300 BPM boundary and confidence reporting prevent arbitrary taps from
  silently changing the project.
- MIDI reference files up to 2 MB are decoded and analyzed in memory only. Tempo, supported meter,
  performed offsets, velocities and event-derived Groove DNA are blended into the current Intent;
  unsupported meters and the 64-bar analysis limit produce explicit warnings.
- A four-point phrase energy editor defines opening, development, peak and landing. The backend
  interpolates it over 1–64 bars and applies it to velocity, ornaments, weak Kick activity, percussion
  density and transitions. An empty curve retains the original automatic tension contour.
- Deterministic Japanese/English musical-language rules support bounce, straight, laid-back, forward,
  simple, complex, human, tight, Funk, hypnotic, development and resolvable surprise directions. Every
  changed dimension, old/new value and reason is returned; unknown language changes nothing.
- All reference inputs transform versioned Intent before generation. They never bypass locks or mutate
  an existing Pattern invisibly.
- Browser audio modules are now loaded only when playback is requested, reducing the initial production
  JavaScript from roughly 504 KB to 254 KB plus on-demand audio chunks.

Remaining research item: audio groove transfer stays disabled until provenance, copyright, consent,
retention and failure-mode policies are defined and an actual audio-analysis pipeline exists.

### Phase 6: blind listening evaluation — implemented

- A consent-gated session compares learned and rule performance using the same Intent, seed, candidate
  index, quantized events and browser playback chain.
- System randomness assigns left/right placement. Before response, public Pattern metadata, analysis and
  identifiers do not disclose the condition; the condition is revealed only after submission.
- If the learned artifact is unavailable and would fall back to the rule model, the session is rejected
  instead of recording a meaningless comparison between identical performance systems.
- Responses remain anonymous and separate from preference learning. Participant group, choice, tie,
  decision time and save-worthy marker are stored, and each session accepts exactly one response.
- Producer, drummer, general-listener and undisclosed results report wins, ties, save rate, median decision
  time and a 95 percent Wilson interval for decisive comparisons.
- The release gate remains `collecting` until all three declared groups have at least 20 completed blocks.
  Learned performance is supported only when every declared group's confidence interval is above chance.
- The gate controls application wording only; it is not a universal measure of musical quality.

### Phase 7: repeatable listening-study blocks — implemented

- A study run now contains six trials. Trials one through five derive distinct seeds from one frozen
  generation request; trial six silently repeats trial one as an anchor retest.
- The server stores a canonical stimulus fingerprint that excludes the compared performance label. A
  `(study_run_id, trial_index)` uniqueness constraint prevents accidental duplicate submissions from
  being counted as new trials.
- Retest agreement is measured by selected performance variant, not screen position, so independently
  randomized left/right placement cannot create false inconsistency.
- Summary data exposes eligible repeat pairs and repeat consistency. Release sample gates count complete
  six-trial blocks rather than treating correlated trials from one block as independent participants.
- Study-run identifiers are random opaque values. They connect trials only inside one block and contain
  no name, email, device fingerprint or cross-session identity.

### Phase 8: technical engine-quality audit — implemented, expanded by Phase 17

- The eight controls exposed in the primary UI are tested at 0.2 and 0.8 over 32 fixed seeds. Each
  corresponding measured-DNA mean must move in the requested direction by at least 0.01.
- The audit exposed inactive Surprise, Movement, Variation and Metric Ambiguity mappings. Structural
  generation now combines a repeated motif stream with a bar-specific stream and uses pulse, motor,
  ambiguity and surprise to shape anchors, weak events, ornaments, percussion and transitions.
- Four selected candidates across five fixed seeds must retain mean pair distance of 0.15 and minimum
  pair distance of 0.08. Rule and learned performance each undergo exact repeated-output checks.
- Five 4-bar/4-candidate rule-mode runs provide a local latency regression gate with a 0.75-second P95
  ceiling. Runtime identity is stored because this number is machine-specific.
- The full report is bundled and tied to the exact engine version. A missing or stale report returns an
  unavailable status instead of reusing obsolete evidence.
- Technical audit status is displayed beside listening-study progress with an explicit statement that
  passing does not establish listener preference.

### Phase 9: procedural browser hi-hat — implemented, superseded by Phase 11

- The previous `square8` oscillator hats were replaced because their pitched rectangular harmonics
  sounded synthetic and harsh.
- Closed and open hats now share a dedicated procedural voice: filtered broadband noise supplies cymbal
  wash while a quiet MetalSynth layer supplies irregular metallic partials.
- Studio Tight uses a brighter high-pass/band-pass pair and shorter envelopes. Warm Pocket uses pink
  noise, lower filter frequencies and longer decay.
- Open-hat decay is independent of the short notation duration, and a later closed hat chokes only an
  actually active open-hat tail. All nodes are disposed when preview stops or another preview claims the
  audio transport.
- Groove-only and Groove-plus-Bass preview use the same implementation. No downloaded or unlicensed
  sample asset is required, and audio code remains lazy-loaded.

### Phase 10: unified browser drum kit and gain safety — implemented

- Duplicate Kick, Snare and Percussion construction in Groove-only and Groove-plus-Bass preview has been
  replaced by one disposable `DrumKitVoice`.
- Kick combines a membrane body with a quiet filtered noise click. Snare combines filtered noise with a
  low membrane body. Percussion has its own tuned membrane envelope, and the recorded hi-hat voice feeds
  the same bus.
- Studio Tight uses shorter, brighter envelopes and Warm Pocket uses lower tuning, pink snare noise and
  longer decay. Velocity controls layer gain without changing canonical backend timing.
- The complete preview, including symbolic Bass where present, passes through a profile gain stage,
  gentle compressor and -1 dB limiter. This reduces clipping when dense drums and Bass coincide.
- Stop, completion, preview switching and error cleanup dispose every synth, filter, dynamics processor
  and output node.

### Phase 11: recorded high-quality hi-hat — implemented

- The remaining pitched `MetalSynth` layer was removed after listening feedback identified a repeating
  beep-like tone. Hi-hat playback now contains no oscillator or synthesized metallic partial.
- Closed and open articulations use separate CC0 studio recordings. The closed source is a 0.217-second
  acoustic hit from karolist/Freesound. The open source is Joseph SARDIN's 48 kHz/24-bit mono recording
  made with a SoundDevices MixPre-3 and Neumann KM184, distributed by BigSoundBank.
- The 14.9-second open source was copied without audio re-encoding to a 1.8-second application asset,
  reducing its size from about 595 KB to 73 KB. Checksums, source pages and licenses are recorded in
  `THIRD_PARTY_NOTICES.md`.
- Separate Samplers retain event velocity, allow overlapping closed hits and release an active open sample
  when a closed event arrives. Studio Tight and Warm Pocket vary duration, filter and level without
  pitch-shifting the recordings.
- Sample loading completes before Transport playback starts. A load failure disposes the entire preview
  graph and reports the existing audio error instead of silently falling back to the synthetic hat.

### Phase 12: deterministic multi-take hi-hat — implemented

- Closed and open articulations now each contain two CC0 acoustic recordings. The additional closed hit
  is a 0.172-second non-produced stereo one-shot by TheEndOfACycle; the additional open hit is Joseph
  SARDIN's matching studio-recorded hi-hat open #2.
- A stable hash of the canonical event ID chooses the take. This removes identical-transient repetition
  without adding nondeterministic playback, so replay, preview comparison and blind-study anchors remain
  reproducible.
- Every take plays at its recorded pitch. Timing and velocity still come from the Pattern; no pitch LFO,
  oscillator or random tuning is used. A fixed -4.5 dB trim on the louder second open recording aligns
  average source level while retaining its acoustic transient and decay.
- Closed hats choke every potentially active open sampler, and a new open hit also releases any previous
  open tail. All four buffers load before playback and all four samplers are disposed on stop or failure.
- Both added files remain local for offline playback. Their source, license, transformation and SHA-256
  are recorded in `THIRD_PARTY_NOTICES.md`.

### Phase 13: coherent recorded Kick and Snare — implemented

- The synthesized Kick membrane/click and Snare noise/body layers have been removed from browser
  previews. Kick and Snare now each use two CC0 acoustic one-shots from one studio-recorded Tama
  Starclassic kit, avoiding a timbral mismatch with the recorded hi-hat.
- A shared deterministic take selector hashes the canonical event ID for Kick, Snare and Hi-hat. The
  Pattern therefore reproduces exactly while repeated hits can contain real transient variation.
- Samples always trigger at their recorded pitch. Pattern velocity supplies dynamics; a fixed -4.5 dB
  trim aligns the stronger Kick source before profile volume and the protected mix bus are applied.
- Studio Tight keeps a brighter Kick and shorter Snare tail. Warm Pocket uses a lower Kick low-pass,
  longer Snare tail and slightly stronger kit bus, without synthesizing replacement partials.
- All eight recorded drum buffers load before Transport playback. Source pages, CC0 licenses and exact
  bundled-file hashes are recorded in `THIRD_PARTY_NOTICES.md` and verified in the production build.

### Phase 14: recorded auxiliary Percussion — implemented

- The last synthesized drum voice was the generic Percussion lane. Generator inspection established that
  this lane produces short weak-beat decorations and normally avoids Kick/Snare collisions.
- Percussion now uses two short CC0 wooden Agogô/block strikes captured with the same studio recorder and
  microphone. Their 0.147- and 0.171-second lengths suit the existing decoration contract without loops,
  stretching or synthetic tails.
- The shared event-ID hash selects a take deterministically. Recorded pitch, Pattern velocity and the
  protected mix bus are preserved; Studio Tight and Warm Pocket differ only in low-cut, level and tail.
- Every browser drum lane is now sample-based except Bass, whose symbolic pitched notes intentionally use
  a synth voice. The former Percussion membrane oscillator has been removed.
- Both files remain local for offline playback, and their sources, CC0 terms and hashes are documented and
  verified in the production output.

### Phase 15: velocity-aware acoustic performance — implemented

- Recorded playback now uses one monotonic velocity-to-gain curve across Kick, Snare, Hi-hat and
  Percussion. `velocity^1.25` keeps full-scale hits unchanged while creating clearer level separation for
  ghost and secondary notes.
- Recorded takes can declare overlapping velocity ranges. Selection chooses the nearest valid layer and
  uses the stable event-ID hash only among equally eligible takes, preserving deterministic replay.
- Kick's softer recording covers 0–0.78 and its stronger recording covers 0.68–1. The overlap avoids an
  audible hard boundary while soft events can no longer trigger the strongest transient.
- Snare and Percussion pairs remain full-range deterministic variations because their recordings are not
  documented as velocity layers. Generated Snare ghost roles already carry low canonical velocities and
  are shaped by the shared curve without hidden role-dependent data changes.
- Boundary, overlap, determinism, monotonicity, silence and unity behavior are covered by pure tests.

### Phase 16: user-controlled drum sound — implemented

- Detailed mode replaces the technical `audio evaluation` selector with a musical `drum sound` choice:
  Tight / clear or Warm / soft. The misleading user-facing `off` option has been removed; it remains an
  API-only value for technical audits that intentionally skip reference rendering.
- Changing the sound on an existing Pattern updates `metadata.render_profile`, invalidates stale analysis
  and requests a fresh evaluation without regenerating or moving any events. Loaded and linked Patterns
  synchronize the selector from their own metadata.
- Easy mode exposes the same two plain-language choices and sends the selected profile into joint Groove
  and Bass generation instead of silently forcing Tight.
- A server-derived evaluation now replaces the current history entry. One sound change therefore creates
  one Undo step rather than a second invisible step for its refreshed analysis.
- UI tests cover easy-mode selection, generation-request propagation and existing-Pattern profile updates.

### Phase 17: complete intent integrity audit — implemented

- The version-bound audit now covers all 21 public Groove DNA dimensions over 32 fixed seeds. A newly
  added field enters the gate automatically and cannot ship as a disconnected control.
- Beat salience shapes strong-versus-weak Hi-hat probability and accent as well as low-end anchors.
  Low-end anchor also shapes Bass/Kick lock; anticipation, omission and hypnotic repetition now cause
  explicit structural changes instead of relying on indirect correlations.
- Repetition recognizes returning motifs such as ABAB. Omission measures missing strong Kick anchors,
  and phrase development measures the per-bar energy contour. Regression tests isolate all three.
- Closed-hat carrier probability was rebalanced away from near-constant saturation. Density, repetition,
  variation and hypnotic controls now retain materially wider, deterministic response ranges while the
  four selected candidates exceed the existing diversity gates.
- The reference renderer uses the browser drum kit's `velocity^1.25` gain curve. Candidate audio scoring
  and audible recorded-drum dynamics therefore agree on velocity response.
- Engine 0.10 / analysis 1.4 passes all 21 directional gates, exact rule/learned determinism, candidate
  diversity and the local latency ceiling. The report still disclaims perceptual superiority.

### Phase 18: precise shaping and state safety — implemented

- The seven advanced musical tabs are now functional. Together they expose all 21 controls with Japanese
  labels, short purpose descriptions and the matching target-to-measured values. The Listener tab shows
  read-only proxy metrics and their caveat.
- The eight main knobs and easy workflow remain unchanged, so precise control does not add friction to
  first-time generation.
- Groove evaluation responses carry a local sequence guard. An older network response cannot overwrite a
  newer edit, generation, candidate choice, regeneration, linked Pattern, Undo or Redo state.
- Bass Generation History uses a unique generation-row ID for option keys and exact retrieval. Repeated
  deterministic Pattern IDs remain valid historical snapshots without React key collisions or ambiguous
  loading.
- Component tests cover full 21-field UI coverage, advanced-control request propagation and reversed
  evaluation responses. Local browser QA confirmed functional tabs, target/measurement layout and zero
  console warnings across 50 retained history records.

### Phase 19: closed-loop personal listening — implemented

- Groove candidates now enter a dedicated score-hidden taste trainer. Both candidates must be auditioned;
  order is randomized, ties are accepted and all six unique pairs from four candidates are presented in
  descending event/DNA distance so early answers carry useful contrast.
- Each presentation owns a client-generated comparison ID and decision time. SQLite enforces that ID as
  unique; exact retries are no-ops and a conflicting reuse is rejected. The server recomputes analysis
  before storing all 21 Groove DNA features rather than trusting the submitted analysis payload.
- Total, decisive, tie and effective comparison counts are separate. Repeated copies of the same feature
  contrast contribute diminishing `sqrt(n)` evidence; ties cannot raise personal influence. Learning
  confidence reaches one only after 25 effective decisive comparisons, and the existing 80-percent
  maximum blend is multiplied by that confidence.
- Candidate cards no longer expose virtual-listener scores beside the personal comparison. The trainer
  explains how many answers are effective, the current confidence, the next-generation blend and the
  most certain preferred ranges.
- Six-trial learned-versus-rule blocks freeze their generation request at trial one. The server also
  enforces participant/configuration consistency, distinct first-five stimuli and an exact trial-six
  anchor repeat. Save-worthy metadata must match the submitted choice.
- Database migrations retain existing comparisons and study rows. Tests cover idempotency, ties, stale
  client analysis, complete 21-field coverage, evidence discounting, frozen blocks, anchor validation,
  pair scheduling and audition gating.

### Phase 20: style-separated Groove and Bass taste — implemented

- Groove answers are stored under the candidates' shared style, and Bass answers under their shared
  behaviour preset. Mixed-style pairs are rejected before storage. Standalone and joint generation ask
  only for the selected scope, so evidence from Funk cannot rank Balanced candidates and evidence from
  Walking cannot rank Supportive Bass.
- Existing rows gain a scope without deletion. Migration resolves both candidate IDs against the nearest
  earlier generation payload and classifies the row when both agree. Unresolvable legacy rows remain in
  the aggregate compatibility profile but are never injected into a style-scoped generation.
- Bass Patterns now retain their generating preset in versioned metadata. Loading a Pattern restores that
  preset, while changing Groove style or Bass behaviour clears the stale comparison set before another
  answer can be submitted.
- The former two-button Bass A/B strip is replaced by a score-hidden listening trainer. Four candidates
  produce all six unique pairs ordered by event/pitch/feature distance; display order is randomized, both
  sides must be auditioned, and a tie is valid. The trainer uses shared Kick/chord context when available
  and falls back to Click rather than judging unmetered Bass in isolation.
- Bass preference storage now matches Groove safety: server-side re-analysis, unique comparison IDs,
  exact-retry no-ops, conflicting-ID rejection, decision time, ties, unique selected vectors, repeated-
  contrast discounting, effective evidence and confidence-gated 80-percent maximum influence.
- OpenAPI types were regenerated. The complete suite passes 155 backend and 46 frontend tests, Ruff,
  TypeScript, ESLint and the production build. Frontend test concurrency is capped at two workers to
  avoid CPU-contention timeouts in constrained environments.

### Phase 21: evidence-backed preference ranges — implemented

- Groove's earlier range approximation and Bass's directional-only score are replaced by one shared
  preference scorer. Both engines can now represent monotonic taste such as “more syncopation” and a
  middle optimum such as “moderate density.” Standalone and joint Bass ranking consume the same result.
- Similar selected candidates alone no longer establish a preferred range. For each feature, the model
  compares the selected candidate's distance from the learned centre with the rejected candidate's
  distance. Contradictory observations cancel, repeated contrasts retain their diminished weight and
  uncertainty can reduce the range's influence to zero.
- Only the three strongest evidence-backed ranges participate. Their combined share grows smoothly with
  `evidence × (1 − uncertainty)` and is capped at 50 percent of the personal score; the already confidence-
  gated personal blend remains unchanged. This prevents a small correlated sample from turning every
  measured feature into a supposed preference.
- Groove and Bass panels sort the same three ranges by ranking strength and disclose “ranking evidence”
  beside uncertainty. The explanation states that coincidental or uncertain similarities do not affect
  ranking, while comparison cards remain score-hidden.
- Tests cover middle optima, low/high symmetry, monotonic fallback, uncertain/unsupported neutrality,
  contradictory evidence cancellation, persisted evidence and final blended candidate ranking for both
  engines.
- The complete regression passes 162 backend and 48 frontend tests, Ruff, TypeScript, ESLint and the
  production build.

### Phase 22: adaptive preference questions — implemented

- The fixed distance-first pair list is replaced by one shared Groove/Bass scheduler. With no evidence,
  it retains the most audibly distinct first pair. After every response it recomputes only the unused
  pairs from the updated style- or preset-scoped profile.
- The explainable information heuristic combines 45-percent audible structural distance, 35-percent
  root-mean-square contrast in weakly known features and 20-percent feature magnitude near the pairwise
  logistic decision boundary. Feature knowledge uses the stronger of evidence-backed range reliability
  and confidence-scaled normalized directional weight.
- The current presentation is frozen while its server response arrives. Completed pair keys are excluded,
  equal scores use a stable key and all six pairs remain available exactly once. Randomized left/right
  placement, both-auditions gating, ties, decision time and idempotent comparison IDs remain unchanged.
- A successful Groove answer now stops its preview before the next comparison, matching Bass and
  preventing sound from the completed pair leaking into the newly selected one.
- No internal score or predicted winner is displayed. Plain-language copy says whether the current pair
  was selected for broad contrast, an unresolved feature or a close preference boundary, and states that
  the remaining questions were selected again after learning.
- Pure tests cover cold start, deterministic ties, unexplored features, learned boundaries and zero-
  evidence contradictory ranges. Component tests prove that Groove and Bass both consume the updated
  profile before choosing a different unused second pair.
- The complete standard regression passes 162 backend and 54 frontend tests, Ruff, TypeScript, ESLint
  and the production build.

### Phase 23: confidence-limited preference-guided search — implemented

- Learned taste now changes what the generator explores, not only how an already-generated pool is
  ranked. Half of each Groove and Bass pool remains on the exact requested Intent; alternating candidates
  use a private preference-guided Intent when learning confidence is at least 20 percent.
- A shared bounded rule moves supported targets by no more than 35 percent, scaled by profile confidence
  and feature signal. Reliable preferred-range centres take precedence over directional extremes, so the
  engine can search for “moderate density” rather than treating every preference as “more” or “less.”
- The private search Intent never becomes the Pattern's public Intent. Guided candidates restore the
  requested Intent and are re-analyzed against it; Bass conflict notes and decision traces are rebuilt as
  well. Metadata records guidance state, maximum strength and contributing features, and candidate cards
  show `好み探索`.
- Groove maps all 21 learned DNA fields. Bass maps eight direct targets; register and aggregate Kick
  relationship remain ranking-only. `allow_chromatic_notes=false` disables chromatic guidance as a hard
  constraint. Standalone Bass, FOLLOW, NEGOTIATE and CO-CREATE all use the same guarded path.
- Tests cover low-confidence neutrality, evidence-backed middle targets, directional fallback, disabled
  features, original-Intent preservation, mixed pools, trace consistency, CO-CREATE propagation and exact
  fixed-profile determinism. The complete regression passes 175 backend and 56 frontend tests, Ruff,
  TypeScript, ESLint and the production build.

### Phase 24: meter-aware rhythmic language — implemented

- Each phrase motif now owns a deterministic three-part figure: an offbeat Kick call, closed-hat answer
  and Percussion turnaround. Repeated motifs reuse their figure, so variation becomes an intelligible
  rhythmic hook rather than unrelated per-instrument randomness.
- Figures select only weak positions from the actual meter subdivision grid. 4/4, 3/4, 5/4, 5/8, 6/8 and
  12/8 therefore receive legal meter-aware landmarks without a hidden sixteenth-note assumption.
- Higher syncopation and motor intent make the call-and-answer pair more likely; variation, surprise,
  interlock and phrase tension shape the turnaround. Core anchors and phrase-ending recovery remain
  protected.
- Tests verify valid weak-grid placement across supported meters and materially more coordinated
  call-and-answer figures under expressive syncopation. The 21-control audit still passes all direction,
  diversity, determinism and latency gates.

### Phase 25: genre-specific rhythmic vocabulary — implemented

- Built-in Funk, Hip Hop, House and Rock now differ in actual arrangement grammar as well as target DNA
  and timing pocket. House provides quarter-note Kick anchors and offbeat hats; Rock supplies a steady
  eighth-note hat spine and beats-one-and-three low end; Hip Hop uses a sparse recurring Kick signature.
- The genre landmarks run only for named built-ins in quarter-note meters. Compound and odd meters retain
  the general meter-aware phrase engine, and user-created style names remain neutral rather than being
  silently forced into a genre.
- House/Rock anchors are applied after omission so soft controls cannot erase their defining pulse.
  Tests prove the exposed preset list, neutral fallback and mandatory structural landmarks for each new
  genre profile. The complete regression passes 186 backend and 57 frontend tests, Ruff, TypeScript,
  ESLint and the production build.

## Evaluation protocol

Compare the previous engine, the upgraded rule engine and later learned-performance variants using
randomized blind A/B trials. Track pairwise win rate, time to a saved candidate, control monotonicity,
candidate diversity, repeat-session preference consistency and latency. Report results separately for
producers, drummers and general listeners; do not collapse them into one universal coolness score.
