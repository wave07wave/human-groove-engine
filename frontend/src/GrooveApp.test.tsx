import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { GrooveApp } from './App'
import { ADVANCED_DNA_GROUPS } from './advancedControls'
import type { GenerateRequest, GrooveIntent, GroovePattern } from './types/generated'

afterEach(() => vi.unstubAllGlobals())

const intent = {
  target_dna: {
    pulse_stability: .7, beat_salience: .7, syncopation: .4, anticipation: .3,
    omission: .2, density: .5, repetition: .7, variation: .3, interlock: .6,
    swing: .2, microtiming: .2, velocity_contrast: .4, duration_contrast: .3,
    low_end_anchor: .7, metric_ambiguity: .2, ghost_density: .2, surprise: .3,
    recovery_strength: .7, motor_affordance: .7, hypnotic: .4, phrase_development: .4,
  },
  tolerance: { default: .12, per_dimension: {} }, priorities: { weights: {} }, movement_target: 'bounce',
} as GrooveIntent

const groove = {
  pattern_id: 'evaluation-race', name: 'Evaluation race groove', bpm: 108, bars: 1,
  meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
  events: [{ event_id: 'kick-1', instrument: 'kick', grid_tick: 0, structural_offset_tick: 0, micro_offset_us: 0, duration_tick: 180, velocity: 100, pitch: 36, primary_role: 'anchor', role_tags: [], accent: .9, timbre_variant: null, duration_style: 'medium', choke_group: null, locked: false, origin: 'generated' }],
  intent,
  metadata: { engine_version: '0.11.0', analysis_version: '1.5', schema_version: '1.0', preset_version: '1.0', rng_algorithm: 'PCG64DXSM', master_seed: 42, style: 'Balanced', performance_model: 'rule-pocket-v1', performance_model_version: '1.0.0', render_profile: 'studio-tight-v1', preference_guided: false, preference_guidance_strength: 0, embodied_operator_arm: 'baseline', knowledge_pack_id: 'neutral-v1', knowledge_pack_version: '1.0', hat_language_profile: 'neutral-hat-v1' },
  analysis: null, instrument_locks: [], bar_locks: [],
} as GroovePattern

it('covers every Groove DNA dimension with grouped detailed controls', () => {
  const controlled = Object.values(ADVANCED_DNA_GROUPS).flatMap(group => group.controls.map(([, key]) => key))
  expect(new Set(controlled)).toEqual(new Set(Object.keys(intent.target_dna)))
})

it('sends a detailed phrase control into the next generation request', async () => {
  const requests: GenerateRequest[] = []
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    if (url === '/api/v1/presets') return Promise.resolve({ ok: true, json: async () => ({ built_in: { Balanced: intent }, user: {} }) } as Response)
    if (url === '/api/v1/generate') {
      const request = JSON.parse(String(init?.body)) as GenerateRequest
      requests.push(request)
      return Promise.resolve({ ok: true, json: async () => ({ candidates: [{ ...groove, intent: request.intent }] }) } as Response)
    }
    return new Promise(() => undefined)
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<GrooveApp />)
  fireEvent.click(await screen.findByRole('button', { name: 'Grooveを作成' }))
  await screen.findByText('Evaluation race groove')
  fireEvent.click(screen.getByRole('button', { name: 'フレーズ' }))
  fireEvent.change(screen.getByLabelText('催眠的な反復'), { target: { value: '.88' } })
  fireEvent.click(screen.getByRole('button', { name: 'Grooveを作成' }))

  await waitFor(() => expect(requests).toHaveLength(2))
  expect(requests[1].intent.target_dna.hypnotic).toBe(.88)
})

it('marks a candidate created by preference-guided search', async () => {
  const guided = {
    ...groove,
    metadata: {
      ...groove.metadata,
      preference_guided: true,
      preference_guidance_strength: .35,
      preference_guided_features: ['density'],
    },
  }
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url === '/api/v1/evaluation/summary' || url === '/api/v1/quality/audit' || url.startsWith('/api/v1/preferences')) {
      return Promise.reject(new Error('not needed in this test'))
    }
    const body = url === '/api/v1/generate'
      ? { candidates: [guided] }
      : { built_in: { Balanced: intent }, user: {} }
    return Promise.resolve({ ok: true, json: async () => body } as Response)
  }))

  render(<GrooveApp />)
  fireEvent.click(await screen.findByRole('button', { name: 'Grooveを作成' }))

  expect(await screen.findByText('好み探索 · 1 events')).toBeTruthy()
})

it('keeps an Easy-mode pattern settings intact when opening detailed editing', async () => {
  const requests: GenerateRequest[] = []
  const externalIntent = {
    ...intent,
    target_dna: { ...intent.target_dna, density: .84, variation: .72 },
  }
  const external = {
    ...groove,
    pattern_id: 'easy-to-detail',
    name: 'Easy mode handoff',
    bpm: 126,
    bars: 4,
    meter: { numerator: 3, denominator: 4, grouping: [2, 2, 2], subdivisions_per_quarter: 3 },
    intent: externalIntent,
    metadata: {
      ...groove.metadata,
      style: 'House',
      performance_model: 'rule-pocket-v1',
      render_profile: 'warm-pocket-v1',
    },
  } as GroovePattern
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (url === '/api/v1/presets') {
      return Promise.resolve({ ok: true, json: async () => ({ built_in: { Balanced: intent, House: intent }, user: {} }) } as Response)
    }
    if (url === '/api/v1/generate') {
      requests.push(JSON.parse(String(init?.body)) as GenerateRequest)
      return Promise.resolve({ ok: true, json: async () => ({ candidates: [external] }) } as Response)
    }
    return Promise.reject(new Error('not needed in this test'))
  }))

  render(<GrooveApp externalPattern={external} />)
  await screen.findByText('Easy mode handoff')
  expect((screen.getByLabelText('BPM') as HTMLInputElement).value).toBe('126')
  expect((screen.getByLabelText('小節数') as HTMLSelectElement).value).toBe('4')
  expect((screen.getByLabelText('拍子') as HTMLSelectElement).value).toBe('3/4')
  expect((screen.getByLabelText('グリッド') as HTMLSelectElement).value).toBe('3')
  expect((screen.getByLabelText('スタイル') as HTMLSelectElement).value).toBe('House')
  expect((screen.getByLabelText('演奏感') as HTMLSelectElement).value).toBe('rule')
  expect((screen.getByLabelText('ドラム音色') as HTMLSelectElement).value).toBe('warm-pocket-v1')

  fireEvent.click(screen.getByRole('button', { name: 'Grooveを作成' }))
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0]).toMatchObject({
    bpm: 126,
    bars: 4,
    meter: { numerator: 3, denominator: 4, subdivisions_per_quarter: 3 },
    preset: 'House',
    performance_mode: 'rule',
    render_profile: 'warm-pocket-v1',
    intent: { target_dna: { density: .84, variation: .72 } },
  })
})

it('ignores an older evaluation response that arrives after a newer edit', async () => {
  const evaluations: { body: GroovePattern, resolve: (value: Response) => void }[] = []
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    if (url === '/api/v1/presets') return Promise.resolve({ ok: true, json: async () => ({ built_in: { Balanced: intent }, user: {} }) } as Response)
    if (url === '/api/v1/generate') return Promise.resolve({ ok: true, json: async () => ({ candidates: [groove] }) } as Response)
    if (url === '/api/v1/evaluate') {
      const body = JSON.parse(String(init?.body)) as GroovePattern
      return new Promise(resolve => evaluations.push({ body, resolve }))
    }
    return new Promise(() => undefined)
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<GrooveApp />)
  fireEvent.click(await screen.findByRole('button', { name: 'Grooveを作成' }))
  await screen.findByText('Evaluation race groove')
  const sound = screen.getByLabelText('ドラム音色') as HTMLSelectElement

  fireEvent.change(sound, { target: { value: 'warm-pocket-v1' } })
  await waitFor(() => expect(evaluations).toHaveLength(1))
  await waitFor(() => expect(sound.value).toBe('warm-pocket-v1'))
  fireEvent.change(sound, { target: { value: 'studio-tight-v1' } })
  await waitFor(() => expect(evaluations).toHaveLength(2))

  await act(async () => evaluations[1].resolve({ ok: true, json: async () => evaluations[1].body } as Response))
  await act(async () => evaluations[0].resolve({ ok: true, json: async () => evaluations[0].body } as Response))

  await waitFor(() => expect(sound.value).toBe('studio-tight-v1'))
})
