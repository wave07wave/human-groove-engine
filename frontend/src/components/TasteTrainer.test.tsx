import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { GroovePattern, GroovePreferenceSummary } from '../types/generated'
import { buildPreferencePairPlans, buildPreferencePairs } from '../utils/tastePairs'
import { TasteTrainer } from './TasteTrainer'

const mocks = vi.hoisted(() => ({
  togglePreview: vi.fn(async (_pattern, onState: (value: boolean) => void) => onState(true)),
  stopGroovePreview: vi.fn((onState: (value: boolean) => void) => onState(false)),
}))

vi.mock('../audio/preview', () => ({
  togglePreview: mocks.togglePreview,
  stopGroovePreview: mocks.stopGroovePreview,
}))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const dna = {
  pulse_stability: .7, beat_salience: .7, syncopation: .4, anticipation: .3,
  omission: .2, density: .5, repetition: .7, variation: .3, interlock: .6,
  swing: .2, microtiming: .2, velocity_contrast: .4, duration_contrast: .3,
  low_end_anchor: .7, metric_ambiguity: .2, ghost_density: .2, surprise: .3,
  recovery_strength: .7, motor_affordance: .7, hypnotic: .4, phrase_development: .4,
}

function candidate(patternId: string, tick: number): GroovePattern {
  return {
    pattern_id: patternId,
    name: patternId,
    bpm: 108,
    bars: 1,
    meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
    events: [{ event_id: `${patternId}-kick`, instrument: 'kick', grid_tick: tick, structural_offset_tick: 0, micro_offset_us: 0, duration_tick: 180, velocity: 100, pitch: 36, primary_role: 'anchor', role_tags: [], accent: .9, timbre_variant: null, duration_style: 'medium', choke_group: null, locked: false, origin: 'generated' }],
    intent: { target_dna: dna, tolerance: { default: .12, per_dimension: {} }, priorities: { weights: {} }, movement_target: 'bounce', phrase_energy_curve: [] },
    metadata: { engine_version: '0.10.0', analysis_version: '1.4', schema_version: '1.0', preset_version: '1.0', rng_algorithm: 'PCG64DXSM', master_seed: 42, style: 'Balanced', performance_model: 'rule-pocket-v1', performance_model_version: '1.0.0', render_profile: 'studio-tight-v1' },
    analysis: { measured_dna: { ...dna, density: Math.min(1, .2 + tick / 2000) } },
    instrument_locks: [],
    bar_locks: [],
  } as unknown as GroovePattern
}

const profile = {
  comparisons: 1,
  decisive_comparisons: 1,
  ties: 0,
  effective_comparisons: 1,
  learning_confidence: .04,
  personal_weight: .032,
  feature_weights: {},
  preferred_ranges: {},
  schema_version: '1.0',
} as GroovePreferenceSummary

it('builds every unique pair and presents the most distinct pairs first', () => {
  const candidates = [candidate('a', 0), candidate('b', 240), candidate('c', 480), candidate('d', 720)]
  const pairs = buildPreferencePairs(candidates)
  const signatures = pairs.map(pair => pair.map(item => item.pattern_id).sort().join('|'))

  expect(pairs).toHaveLength(6)
  expect(new Set(signatures).size).toBe(6)
})

it('requires both auditions and records an idempotent tie comparison', async () => {
  const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => ({
    ok: true,
    json: async () => ({ ...profile, comparisons: 2, ties: 1 }),
    requestBody: init?.body,
  } as unknown as Response))
  const onPreference = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<TasteTrainer candidates={[candidate('a', 0), candidate('b', 480)]} preference={profile} onPreference={onPreference}/>)

  const tie = screen.getByRole('button', { name: '差がない' }) as HTMLButtonElement
  expect(tie.disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '比較候補 1 を再生' }))
  await waitFor(() => expect(mocks.togglePreview).toHaveBeenCalledTimes(1))
  expect(tie.disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '比較候補 2 を再生' }))
  await waitFor(() => expect(tie.disabled).toBe(false))
  fireEvent.click(tie)

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
  expect(body.selected).toBe('tie')
  expect(body.comparison_id).toMatch(/^[A-Za-z0-9-]{8,64}$/)
  expect(body.decision_time_ms).toBeGreaterThanOrEqual(250)
  expect(body.display_order).toEqual([body.candidate_a.pattern_id, body.candidate_b.pattern_id])
  expect(onPreference).toHaveBeenCalledWith(expect.objectContaining({ comparisons: 2, ties: 1 }))
  expect(mocks.stopGroovePreview).toHaveBeenCalledOnce()
  expect(screen.getByText('好みを学習しました')).toBeTruthy()
})

it('shows how strongly a preferred range can affect ranking', () => {
  const learned = {
    ...profile,
    preferred_ranges: {
      density: { mean: .5, low: .4, high: .6, uncertainty: .2, observations: 8, evidence: .9 },
    },
  } as GroovePreferenceSummary

  render(<TasteTrainer candidates={[]} preference={learned} onPreference={vi.fn()}/>)

  expect(screen.getByText('順位への根拠 72% · 不確かさ 20%')).toBeTruthy()
  expect(screen.getByText(/偶然似ただけの特徴や不確かな帯は反映しません/)).toBeTruthy()
})

it('re-ranks the remaining Groove pairs after each learned answer', async () => {
  const candidates = [candidate('a', 0), candidate('b', 240), candidate('c', 720)]
  const learned = {
    ...profile,
    comparisons: 12,
    learning_confidence: .8,
    feature_weights: { density: 8 },
    preferred_ranges: {
      density: { mean: .45, low: .35, high: .55, uncertainty: .1, observations: 8, evidence: .9 },
    },
  } as GroovePreferenceSummary
  const first = buildPreferencePairPlans(candidates, profile)[0]
  const expectedNext = buildPreferencePairPlans(candidates, learned)
    .find(item => item.key !== first.key)
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => ({
    ok: true,
    json: async () => learned,
    requestUrl: String(input),
    requestBody: init?.body,
  } as unknown as Response))
  const onPreference = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const view = render(
    <TasteTrainer candidates={candidates} preference={profile} onPreference={onPreference}/>,
  )

  fireEvent.click(screen.getByRole('button', { name: '比較候補 1 を再生' }))
  await waitFor(() => expect(mocks.togglePreview).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('button', { name: '比較候補 2 を再生' }))
  await waitFor(() => expect(mocks.togglePreview).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: '候補 1 が好き' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

  view.rerender(
    <TasteTrainer candidates={candidates} preference={learned} onPreference={onPreference}/>,
  )
  fireEvent.click(screen.getByRole('button', { name: '次の組み合わせ' }))
  expect(screen.getByText(/比較 2\/3/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '比較候補 1 を再生' }))
  await waitFor(() => expect(mocks.togglePreview).toHaveBeenCalledTimes(3))
  fireEvent.click(screen.getByRole('button', { name: '比較候補 2 を再生' }))
  await waitFor(() => expect(mocks.togglePreview).toHaveBeenCalledTimes(4))
  fireEvent.click(screen.getByRole('button', { name: '差がない' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

  const secondBody = JSON.parse(String(fetchMock.mock.calls[1][1]?.body))
  expect([secondBody.candidate_a.pattern_id, secondBody.candidate_b.pattern_id].sort()).toEqual(
    expectedNext?.pair.map(item => item.pattern_id).sort(),
  )
})
