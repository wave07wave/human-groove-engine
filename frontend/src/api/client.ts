import type { BassGenerateRequest, BassGenerateResponse, BassGenerationRecord, BassMutationOperation, BassPattern, BassPatternExchange, BassPreferenceRecord, BassPreferenceSummary, BassPreserveOptions, BassPresetsResponse, GenerateRequest, GrooveContext, GroovePattern, Instrument, IntegrationMode, JointGenerateResponse, PresetsResponse } from '../types/generated'

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  return response.json() as Promise<T>
}

export const api = {
  presets: () => json<PresetsResponse>('/api/v1/presets'),
  generate: (body: GenerateRequest) => json<{ candidates: GroovePattern[] }>('/api/v1/generate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  evaluate: (pattern: GroovePattern) => json<GroovePattern>('/api/v1/evaluate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern),
  }),
  mutate: (pattern: GroovePattern, instruments: Instrument[], bars: number[]) => json<GroovePattern>('/api/v1/mutate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pattern, instruments, bars, operation: 'regenerate' }),
  }),
  prefer: (a: GroovePattern, b: GroovePattern, selected: 'A' | 'B') => json('/api/v1/preferences', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_a: a, candidate_b: b, selected, display_order: ['A', 'B'] }),
  }),
  savePreset: (name: string, intent: GroovePattern['intent']) => json('/api/v1/presets', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, intent }),
  }),
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
  generationPattern: (patternId: string) => json<BassPattern>(`/api/v1/bass/history/generations/${encodeURIComponent(patternId)}`),
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
    body: JSON.stringify({ groove_pattern: groovePattern, bass_request: bassRequest, mode, shared_complexity_budget: sharedComplexityBudget, bass_complexity_share: bassComplexityShare, candidate_count: bassRequest.candidate_count }),
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
  preferences: () => json<BassPreferenceSummary>('/api/v1/bass/preferences'),
  prefer: (a: BassPattern, b: BassPattern, selected: 'A' | 'B', displayOrder = [a.pattern_id, b.pattern_id]) => json<BassPreferenceSummary>('/api/v1/bass/preferences', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_a: a, candidate_b: b, selected, display_order: displayOrder }),
  }),
  async midi(pattern: BassPattern, channel = 0) {
    const response = await fetch(`/api/v1/bass/export-midi?channel=${channel}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) })
    if (!response.ok) throw new Error(await response.text())
    const href = URL.createObjectURL(await response.blob())
    const link = document.createElement('a'); link.href = href; link.download = `${pattern.name}.mid`; link.click()
    URL.revokeObjectURL(href)
  },
}
