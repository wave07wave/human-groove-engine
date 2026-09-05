/* Thin application aliases over src/types/openapi.ts, generated from FastAPI/Pydantic. */
import type { components } from './openapi'

type Schema = components['schemas']

export type Instrument = Schema['InstrumentID']
export type EventRole = Schema['EventRole']
export type GrooveDNA = Schema['GrooveDNA']
export type MeterDefinition = Schema['MeterDefinition']
export type ListenerAnalysis = Schema['ListenerAnalysis']
export type EmbodiedIntent = { challenge:number, renewal:number, timing_coherence:number, low_end_motion:number, meter_familiarity:number, style_familiarity:number }
type MetricLevel = { clarity:number, phase_stability:number, activity:number }
export type EmbodiedGrooveFeatures = {
  schema_version:string
  motor_scaffold:{ subdivision:MetricLevel, tactus:MetricLevel, half_time:MetricLevel, bar_cycle:MetricLevel }
  prediction_error:{ event_surprise:number, omission_surprise:number, concentration:number, recoverable_ratio:number, context_confidence:number }
  timing_coherence:{ lane_offsets_ms:Record<string,number>, within_lane_dispersion:number, pairwise_phase_coherence:number, shared_drift:number, independent_jitter:number, coherence:number }
  low_end_motion:{ symbolic_coupling:number, spectral_flux_50_100hz:number|null, onset_coherence:number|null, envelope_cycle:number|null, render_applicable:boolean }
  phrase_renewal:{ motif_memory:number, layer_entry_lift:number, challenge_strength:number, reentry_strength:number }
  estimates:{ urge_to_move_prior:number, pleasure_prior:number, uncertainty:number, caveat:string }
}
export type MotorTempoProfile = { bpm:number, interval_ms:number, dispersion:number, confidence:number, tempo_aliases:number[], accepted_taps:number, caveat:string }
export type EmbodiedOperatorSummary = { operator_arm:string, evaluations:number, average_urge_to_move:number, average_pleasure:number, average_beat_clarity:number }
export type EmbodiedEvaluationSummary = { total_evaluations:number, operator_arms:EmbodiedOperatorSummary[], minimum_evaluations_per_arm:number, sufficient_for_personal_comparison:boolean, caveat:string }
export type EmbodiedEvaluationResult = { accepted:boolean, evidence_class:'self_report'|'tap'|'motion', caveat:string }
export type GrooveAnalysis = Omit<Schema['GrooveAnalysis-Output'], 'confidence'> & {
  confidence: Schema['AnalysisConfidence']
  embodied?: EmbodiedGrooveFeatures | null
}

export type GrooveIntent = Omit<Schema['GrooveIntent'], 'target_dna' | 'tolerance' | 'priorities'> & {
  target_dna: GrooveDNA
  tolerance: Omit<Schema['GrooveTolerance'], 'default' | 'per_dimension'> & {
    default: number
    per_dimension: Record<string, number>
  }
  priorities: Omit<Schema['GroovePriority'], 'weights'> & {
    weights: Record<string, number>
  }
  embodied?: EmbodiedIntent
}

export type GrooveEvent = Omit<Schema['GrooveEvent'], 'event_id' | 'role_tags' | 'pitch' | 'timbre_variant' | 'choke_group'> & {
  event_id: string
  role_tags: EventRole[]
  pitch: number | null
  timbre_variant: string | null
  choke_group: string | null
}

export type DetroitSoulMode = 'standard' | 'benny' | 'pistol' | 'uriel' | 'blend'
export type DetroitSoulBlend = { benny: number, pistol: number, uriel: number }
export type DetroitSoulSettings = { mode: DetroitSoulMode, blend: DetroitSoulBlend }

type PatternOutput = Schema['GroovePattern-Output']
export type GroovePattern = Omit<PatternOutput, 'events' | 'intent' | 'analysis' | 'instrument_locks' | 'bar_locks' | 'metadata'> & {
  events: GrooveEvent[]
  intent: GrooveIntent
  analysis: GrooveAnalysis | null
  instrument_locks: Instrument[]
  bar_locks: number[]
  /** Optional only while reading patterns saved before Detroit Soul styles existed. */
  metadata: PatternOutput['metadata'] & { detroit_soul?: DetroitSoulSettings }
}

export type GenerateRequest = Omit<Schema['GenerateRequest'], 'meter' | 'intent' | 'render_profile' | 'candidate_strategy'> & {
  meter: MeterDefinition
  intent: GrooveIntent
  render_profile: 'studio-tight-v1' | 'warm-pocket-v1' | 'club-punch-v1' | 'vintage-dust-v1'
  /** The API defaults to quality; Easy mode opts into controlled exploration. */
  candidate_strategy?: 'quality' | 'explore'
  anonymous_session_id?: string
  detroit_soul?: DetroitSoulSettings
}
export type GroovePreferenceSummary = Schema['GroovePreferenceSummary']
export type TapAnalysis = Omit<Schema['TapAnalysis'], 'suggested_intent'> & {
  suggested_intent: GrooveIntent
}
export type MidiReferenceAnalysis = Omit<Schema['MidiReferenceAnalysis'], 'suggested_intent'> & {
  suggested_intent: GrooveIntent
}
export type IntentTransformResponse = Omit<Schema['IntentTransformResponse'], 'intent' | 'changes'> & {
  intent: GrooveIntent
  changes: Schema['IntentChange'][]
}
export type GenerateResponse = Omit<Schema['GenerateResponse'], 'candidates'> & {
  candidates: GroovePattern[]
  preference_profile: GroovePreferenceSummary | null
}
export type ParticipantGroup = Schema['BlindSessionRequest']['participant_group']
export type BlindSession = Omit<Schema['BlindSession'], 'candidates'> & {
  candidates: (Omit<Schema['BlindCandidate'], 'pattern'> & { pattern: GroovePattern })[]
}
export type BlindResponseResult = Schema['BlindResponseResult']
export type EvaluationSummary = Schema['EvaluationSummary']
export type QualityAuditReport = Schema['QualityAuditReport']
export type PresetsResponse = Omit<Schema['PresetsResponse'], 'built_in' | 'user'> & {
  built_in: Record<string, GrooveIntent>
  user: Record<string, GrooveIntent>
}

export type BassIntentDNA = Schema['BassIntentDNA']
export type MotownBassMode = 'standard' | 'jamerson'
export type MotownBassSettings = { mode: MotownBassMode }
export type BassIntent = Omit<Schema['BassIntent'], 'target' | 'tolerances' | 'priorities'> & {
  target: BassIntentDNA
  tolerances: Schema['BassTolerance']
  priorities: Schema['BassPriority']
}
export type BassEvent = Omit<Schema['BassEvent-Output'], 'articulation' | 'locks' | 'provenance'> & {
  articulation: Schema['BassArticulation']
  locks: Schema['EventLocks']
  provenance: Schema['EventProvenance']
}
export type BassAnalysis = Schema['BassAnalysis-Output']
type BassPatternOutput = Schema['BassPattern-Output']
export type BassPattern = Omit<BassPatternOutput, 'events' | 'intent' | 'analysis' | 'intent_locks' | 'structural_events' | 'register_limits' | 'metadata'> & {
  events: BassEvent[]
  intent: BassIntent
  analysis: BassAnalysis | null
  intent_locks: Schema['BassIntentLocks']
  structural_events: Schema['BassStructuralEvent'][]
  register_limits: Schema['RegisterLimits']
  /** Optional only while reading Bass patterns saved before Motown styles existed. */
  metadata: BassPatternOutput['metadata'] & { motown_bass?: MotownBassSettings }
}
export type BassGenerateRequest = Omit<Schema['BassGenerateRequest'], 'meter' | 'intent' | 'register_limits' | 'motown_bass'> & {
  meter: MeterDefinition
  intent: BassIntent
  register_limits: Schema['RegisterLimits']
  motown_bass?: MotownBassSettings
}
export type BassMutationOperation = Schema['MutationOperation']
export type BassVoicePolicy = Schema['BassVoicePolicy']
export type BassPreserveOptions = Schema['BassPreserveOptions']
export type BassIntentLocks = Schema['BassIntentLocks']
export type BassPreferenceSummary = Schema['BassPreferenceSummary']
export type BassPatternExchange = Omit<Schema['BassPatternExchange-Output'], 'pattern'> & { pattern: BassPattern }
export type BassIntentExchange = Omit<Schema['BassIntentExchange-Output'], 'intent'> & { intent: BassIntent }
export type BassPresetExchange = Omit<Schema['BassPresetExchange-Output'], 'intent'> & { intent: BassIntent }
export type BassGenerationRecord = Schema['BassGenerationRecord']
export type BassPreferenceRecord = Schema['BassPreferenceRecord']
export type BassGenerateResponse = Omit<Schema['BassGenerateResponse'], 'candidates'> & {
  candidates: BassPattern[]
}
export type GrooveContext = Schema['GrooveContext-Output']
export type IntegrationMode = Schema['IntegrationMode']
export type JointGenerationResult = Omit<Schema['JointGenerationResult'], 'groove_pattern' | 'bass_pattern'> & {
  groove_pattern: GroovePattern
  bass_pattern: BassPattern
}
export type JointGenerateResponse = Omit<Schema['JointGenerateResponse'], 'candidates'> & {
  candidates: JointGenerationResult[]
}
export type BassPresetsResponse = {
  built_in: Record<string, BassIntent>
  user: Record<string, BassIntent>
}

export type KeyboardStyleMode = 'standard' | 'earl' | 'joe' | 'johnny' | 'bill_evans' | 'blend'
export type KeyboardBlend = { earl: number, joe: number, johnny: number }
export type BillEvansProfile = 'lyrical_ballad' | 'interactive_trio' | 'solo_reflective' | 'waltz' | 'uptempo'
export type BillEvansSettings = { profile: BillEvansProfile, chord_retention: number, performance_context: 'solo' | 'trio_with_bass' | 'full_trio' }
export type DetroitKeyboardSettings = { mode: KeyboardStyleMode, blend: KeyboardBlend, bill_evans?: BillEvansSettings }
export type KeyboardInstrument = Schema['KeyboardEvent']['instrument']
export type KeyboardEvent = Schema['KeyboardEvent']
export type KeyboardAnalysis = Schema['KeyboardAnalysis']
export type KeyboardRhythmContext = Required<Schema['KeyboardRhythmContext']>
type KeyboardPatternOutput = Schema['KeyboardPattern-Output']
export type KeyboardPattern = Omit<KeyboardPatternOutput, 'metadata' | 'analysis' | 'rhythm_context' | 'bar_locks'> & {
  metadata: KeyboardPatternOutput['metadata'] & { detroit_keyboard?: DetroitKeyboardSettings }
  analysis: KeyboardAnalysis | null
  rhythm_context: KeyboardRhythmContext
  bar_locks: number[]
}
export type KeyboardGenerateRequest = Omit<Schema['KeyboardGenerateRequest'], 'meter' | 'detroit_keyboard' | 'rhythm_context'> & {
  meter: MeterDefinition
  detroit_keyboard?: DetroitKeyboardSettings
  rhythm_context?: KeyboardRhythmContext
}
export type KeyboardGenerateResponse = Omit<Schema['KeyboardGenerateResponse'], 'candidates'> & {
  candidates: KeyboardPattern[]
}
export type KeyboardGenerationRecord = Schema['KeyboardGenerationRecord']
export type KeyboardPatternExchange = Omit<Schema['KeyboardPatternExchange-Output'], 'pattern'> & {
  pattern: KeyboardPattern
}
