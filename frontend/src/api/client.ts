import type { BassGenerateRequest, BassGenerateResponse, BassGenerationRecord, BassMutationOperation, BassPattern, BassPatternExchange, BassPreferenceRecord, BassPreferenceSummary, BassPreserveOptions, BassPresetsResponse, BlindResponseResult, BlindSession, EmbodiedEvaluationResult, EmbodiedEvaluationSummary, EvaluationSummary, GenerateRequest, GenerateResponse, GrooveContext, GrooveIntent, GroovePattern, GroovePreferenceSummary, Instrument, IntegrationMode, IntentTransformResponse, JointGenerateResponse, MidiReferenceAnalysis, MotorTempoProfile, ParticipantGroup, PresetsResponse, QualityAuditReport, TapAnalysis } from '../types/generated'

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  return response.json() as Promise<T>
}

export const api = {
  presets: () => json<PresetsResponse>('/api/v1/presets'),
  generate: (body: GenerateRequest) => json<GenerateResponse>('/api/v1/generate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  evaluate: (pattern: GroovePattern) => json<GroovePattern>('/api/v1/evaluate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern),
  }),
  mutate: (pattern: GroovePattern, instruments: Instrument[], bars: number[]) => json<GroovePattern>('/api/v1/mutate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pattern, instruments, bars, operation: 'regenerate' }),
  }),
  preferences: (style?: string) => json<GroovePreferenceSummary>(
    `/api/v1/preferences${style ? `?style=${encodeURIComponent(style)}` : ''}`,
  ),
  prefer: (a: GroovePattern, b: GroovePattern, selected: 'A' | 'B' | 'tie', displayOrder: string[], comparisonId: string, decisionTimeMs: number) => json<GroovePreferenceSummary>('/api/v1/preferences', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_a: a, candidate_b: b, selected, display_order: displayOrder, comparison_id: comparisonId, decision_time_ms: decisionTimeMs }),
  }),
  savePreset: (name: string, intent: GroovePattern['intent']) => json('/api/v1/presets', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, intent }),
  }),
  analyzeTaps: (timestamps: number[], currentIntent: GrooveIntent) => json<TapAnalysis>('/api/v1/reference/taps', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ timestamps_ms: timestamps, current_intent: currentIntent }) }),
  analyzeMidi: (filename: string, midiBase64: string, currentIntent: GrooveIntent) => json<MidiReferenceAnalysis>('/api/v1/reference/midi', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename, midi_base64: midiBase64, current_intent: currentIntent }) }),
  transformIntent: (text: string, currentIntent: GrooveIntent) => json<IntentTransformResponse>('/api/v1/intent/transform', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, current_intent: currentIntent }) }),
  startEvaluation: (participantGroup: ParticipantGroup, generation: GenerateRequest, studyRunId: string, trialIndex: number) => json<BlindSession>('/api/v1/evaluation/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ participant_group: participantGroup, consent: true, generation, study_run_id: studyRunId, trial_index: trialIndex }) }),
  submitEvaluation: (sessionId: string, selected: 'left'|'right'|'tie', decisionTimeMs: number, savedChoice: 'left'|'right'|'none') => json<BlindResponseResult>('/api/v1/evaluation/responses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, selected, decision_time_ms: decisionTimeMs, saved_choice: savedChoice }) }),
  evaluationSummary: () => json<EvaluationSummary>('/api/v1/evaluation/summary'),
  embodiedEvaluationSummary: (anonymousSessionId: string) => json<EmbodiedEvaluationSummary>(`/api/v1/evaluation/embodied/summary?anonymous_session_id=${encodeURIComponent(anonymousSessionId)}`),
  calibrateMotorTempo: (anonymousSessionId: string, timestamps: number[]) => json<MotorTempoProfile>('/api/v1/evaluation/motor-tempo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ anonymous_session_id: anonymousSessionId, timestamps_ms: timestamps }) }),
  submitEmbodiedEvaluation: (body: { anonymous_session_id:string, pattern:GroovePattern, urge_to_move:number, pleasure:number, beat_clarity:number, familiarity?:number, style_liking?:number, listening_context:'unknown'|'headphones'|'speakers', posture:'unknown'|'seated'|'standing', motion_consent:boolean, tap_observation?:{ phase_error:number|null, period_error:number|null, variability:number|null }, motion_observation?:{ periodic_energy:number, movement_energy:number, device_quality:number } }) => json<EmbodiedEvaluationResult>('/api/v1/evaluation/embodied', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  qualityAudit: () => json<QualityAuditReport>('/api/v1/quality/audit'),
  async midi(pattern: GroovePattern) {
    const response = await fetch('/api/v1/export-midi', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) })
    if (!response.ok) throw new Error(await response.text())
    const href = URL.createObjectURL(await response.blob())
    const link = document.createElement('a'); link.href = href; link.download = `${pattern.name}.mid`; link.click()
    URL.revokeObjectURL(href)
  },
}

export const bassApi = {
  presets: () => json<BassPresetsResponse>('/api/v1/bass/presets'),
  savePreset: (name: string, intent: BassPattern['intent']) => json<{ saved: string }>('/api/v1/bass/presets', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, intent }),
  }),
  patterns: () => json<BassPattern[]>('/api/v1/bass/patterns'),
  savePattern: (pattern: BassPattern) => json<BassPattern>('/api/v1/bass/patterns', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern),
  }),
  async deletePattern(patternId: string) {
    const response = await fetch(`/api/v1/bass/patterns/${encodeURIComponent(patternId)}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  },
  generationHistory: (limit = 50) => json<BassGenerationRecord[]>(`/api/v1/bass/history/generations?limit=${limit}`),
  generationPattern: (generationId: number) => json<BassPattern>(`/api/v1/bass/history/generation-records/${generationId}`),
  preferenceHistory: (limit = 50) => json<BassPreferenceRecord[]>(`/api/v1/bass/history/preferences?limit=${limit}`),
  exportPattern: (pattern: BassPattern) => json<BassPatternExchange>('/api/v1/bass/exchange/pattern/export', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern),
  }),
  importPattern: (exchange: BassPatternExchange) => json<BassPattern>('/api/v1/bass/exchange/pattern/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(exchange),
  }),
  contextFromGroove: (pattern: GroovePattern) => json<GrooveContext>('/api/v1/bass/context/from-groove', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern),
  }),
  jointGenerate: (groovePattern: GroovePattern, bassRequest: BassGenerateRequest, mode: IntegrationMode, sharedComplexityBudget: number, bassComplexityShare: number) => json<JointGenerateResponse>('/api/v1/interaction/generate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ groove_pattern: groovePattern, bass_request: bassRequest, mode, shared_complexity_budget: sharedComplexityBudget, bass_complexity_share: bassComplexityShare, candidate_count: bassRequest.candidate_count, reference_render_analysis: true }),
  }),
  generate: (body: BassGenerateRequest) => json<BassGenerateResponse>('/api/v1/bass/generate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  evaluate: (pattern: BassPattern) => json<BassPattern>('/api/v1/bass/evaluate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern),
  }),
  mutate: (pattern: BassPattern, bars: number[], operation: BassMutationOperation, preserve: BassPreserveOptions) => json<BassPattern>('/api/v1/bass/mutate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pattern, bars, operation, preserve }),
  }),
  refine: (pattern: BassPattern, strength = .35) => json<BassPattern>('/api/v1/bass/refine', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pattern, strength }),
  }),
  preferences: (preset?: string) => json<BassPreferenceSummary>(
    `/api/v1/bass/preferences${preset ? `?preset=${encodeURIComponent(preset)}` : ''}`,
  ),
  prefer: (a: BassPattern, b: BassPattern, selected: 'A' | 'B' | 'tie', displayOrder: string[], comparisonId: string, decisionTimeMs: number) => json<BassPreferenceSummary>('/api/v1/bass/preferences', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_a: a, candidate_b: b, selected, display_order: displayOrder, comparison_id: comparisonId, decision_time_ms: decisionTimeMs }),
  }),
  async midi(pattern: BassPattern, channel = 0) {
    const response = await fetch(`/api/v1/bass/export-midi?channel=${channel}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) })
    if (!response.ok) throw new Error(await response.text())
    const href = URL.createObjectURL(await response.blob())
    const link = document.createElement('a'); link.href = href; link.download = `${pattern.name}.mid`; link.click()
    URL.revokeObjectURL(href)
  },
}
