/* Thin application aliases over src/types/openapi.ts, generated from FastAPI/Pydantic. */
import type { components } from './openapi'

type Schema = components['schemas']

export type Instrument = Schema['InstrumentID']
export type EventRole = Schema['EventRole']
export type GrooveDNA = Schema['GrooveDNA']
export type MeterDefinition = Schema['MeterDefinition']
export type ListenerAnalysis = Schema['ListenerAnalysis']
export type GrooveAnalysis = Omit<Schema['GrooveAnalysis'], 'confidence'> & {
  confidence: Schema['AnalysisConfidence']
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
}

export type GrooveEvent = Omit<Schema['GrooveEvent'], 'event_id' | 'role_tags' | 'pitch' | 'timbre_variant' | 'choke_group'> & {
  event_id: string
  role_tags: EventRole[]
  pitch: number | null
  timbre_variant: string | null
  choke_group: string | null
}

type PatternOutput = Schema['GroovePattern-Output']
export type GroovePattern = Omit<PatternOutput, 'events' | 'intent' | 'analysis' | 'instrument_locks' | 'bar_locks'> & {
  events: GrooveEvent[]
  intent: GrooveIntent
  analysis: GrooveAnalysis | null
  instrument_locks: Instrument[]
  bar_locks: number[]
}

export type GenerateRequest = Omit<Schema['GenerateRequest'], 'meter' | 'intent'> & {
  meter: MeterDefinition
  intent: GrooveIntent
}
export type PresetsResponse = Omit<Schema['PresetsResponse'], 'built_in' | 'user'> & {
  built_in: Record<string, GrooveIntent>
  user: Record<string, GrooveIntent>
}

export type BassIntentDNA = Schema['BassIntentDNA']
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
export type BassPattern = Omit<Schema['BassPattern-Output'], 'events' | 'intent' | 'analysis' | 'intent_locks' | 'structural_events' | 'register_limits'> & {
  events: BassEvent[]
  intent: BassIntent
  analysis: BassAnalysis | null
  intent_locks: Schema['BassIntentLocks']
  structural_events: Schema['BassStructuralEvent'][]
  register_limits: Schema['RegisterLimits']
}
export type BassGenerateRequest = Omit<Schema['BassGenerateRequest'], 'meter' | 'intent' | 'register_limits'> & {
  meter: MeterDefinition
  intent: BassIntent
  register_limits: Schema['RegisterLimits']
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
