import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { BassPattern, BassPreferenceSummary } from '../types/generated'
import { buildBassPreferencePairPlans, buildBassPreferencePairs } from '../utils/bassTastePairs'
import { BassTasteTrainer } from './BassTasteTrainer'

const mocks = vi.hoisted(() => ({
  toggleBassPreview: vi.fn(async (
    _pattern, _mode, onState: (value: boolean) => void,
  ) => onState(true)),
  stopBassPreview: vi.fn((onState: (value: boolean) => void) => onState(false)),
}))

vi.mock('../audio/bassPreview', () => ({
  toggleBassPreview: mocks.toggleBassPreview,
  stopBassPreview: mocks.stopBassPreview,
}))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

function candidate(patternId: string, tick: number, pitch: number): BassPattern {
  return {
    pattern_id: patternId,
    name: patternId,
    bpm: 108,
    bars: 1,
    meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
    tempo_map: { segments: [{ start_tick: 0, bpm: 108 }] },
    harmony: { events: [] },
    key_context: null,
    input_mode: 'key_mode',
    events: [{
      event_id: `${patternId}-event`, grid_tick: tick, structural_offset_tick: 0,
      micro_offset_us: 0, duration_tick: 240, pitch, velocity: 92,
      harmonic_role: 'root', rhythmic_role: 'anchor',
      articulation: { connection: 'normal', technique: 'normal', accent: 'normal', legato_overlap_tick: 0 },
      structural_weight: .8, phrase_id: 'phrase-0', motif_id: 'motif-0',
      approach_target_id: null, locks: {}, provenance: { origin: 'generated', generator_stage: 'performance' },
      decision_trace: null,
    }],
    structural_events: [],
    intent: {}, intent_locks: {},
    register_limits: { lowest_midi_note: 28, highest_midi_note: 60, preferred_center: 42, preferred_zone: 'core', max_single_leap: 12 },
    voice_policy: 'monophonic_retrigger',
    metadata: { engine_version: '0.1', schema_version: '1.0', analysis_version: '0.1', preset_version: '1.0', rng_algorithm: 'PCG64DXSM', master_seed: 42, preset: 'Supportive', candidate_index: 0, revision: 0, resolved_intent_notes: [] },
    analysis: {
      atomic: { syncopation_index: tick / 960, onset_density: .3, silence_ratio: .6, root_ratio: .8, chromatic_ratio: 0, register_mean: pitch, duration_variance: tick },
      dna: { melodic_motion: pitch / 60, kick_relationship_quality: .7, timing_character_strength: tick / 960 },
    },
    groove_context: {
      tempo_map: { segments: [{ start_tick: 0, bpm: 108 }] },
      meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
      phrase_boundaries: [], beat_map: [], metric_gravity: [], tension_curve: [],
      kick_events: [{ grid_tick: 0, structural_offset_tick: 0, micro_offset_us: 0, velocity: 100 }],
      groove_dna: {},
    },
    interaction_analysis: null,
  } as unknown as BassPattern
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
  profile_scope: 'Supportive',
  schema_version: '1.0',
} as BassPreferenceSummary

it('builds every unique Bass pair once', () => {
  const candidates = [
    candidate('a', 0, 36), candidate('b', 240, 38),
    candidate('c', 480, 41), candidate('d', 720, 43),
  ]
  const pairs = buildBassPreferencePairs(candidates)
  const signatures = pairs.map(pair => pair.map(item => item.pattern_id).sort().join('|'))

  expect(pairs).toHaveLength(6)
  expect(new Set(signatures).size).toBe(6)
})

it('requires both Bass auditions and safely records a tie', async () => {
  const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => ({
    ok: true,
    json: async () => ({ ...profile, comparisons: 2, ties: 1 }),
    requestBody: init?.body,
  } as unknown as Response))
  const onPreference = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<BassTasteTrainer candidates={[
    candidate('a', 0, 36), candidate('b', 480, 43),
  ]} preference={profile} onPreference={onPreference}/>)

  const tie = screen.getByRole('button', { name: '差がない' }) as HTMLButtonElement
  expect(tie.disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Bass比較候補 1 を再生' }))
  await waitFor(() => expect(mocks.toggleBassPreview).toHaveBeenCalledTimes(1))
  expect(tie.disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Bass比較候補 2 を再生' }))
  await waitFor(() => expect(tie.disabled).toBe(false))
  fireEvent.click(tie)

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
  expect(body.selected).toBe('tie')
  expect(body.comparison_id).toMatch(/^[A-Za-z0-9-]{8,64}$/)
  expect(body.decision_time_ms).toBeGreaterThanOrEqual(250)
  expect(body.display_order).toEqual([body.candidate_a.pattern_id, body.candidate_b.pattern_id])
  expect(mocks.toggleBassPreview.mock.calls[0][1]).toBe('bass_kick')
  expect(onPreference).toHaveBeenCalledWith(expect.objectContaining({ comparisons: 2, ties: 1 }))
  expect(screen.getByText('このスタイルの好みを学習しました')).toBeTruthy()
})

it('shows how strongly a Bass range can affect ranking', () => {
  const learned = {
    ...profile,
    preferred_ranges: {
      syncopation: {
        mean: .5, low: .4, high: .6, uncertainty: .25, observations: 9, evidence: .8,
      },
    },
  } as BassPreferenceSummary

  render(<BassTasteTrainer candidates={[]} preference={learned} onPreference={vi.fn()}/>)

  expect(screen.getByText('順位への根拠 60% · 不確かさ 25%')).toBeTruthy()
  expect(screen.getByText(/偶然似ただけの特徴や不確かな帯は反映しません/)).toBeTruthy()
})

it('re-ranks the remaining Bass pairs after each learned answer', async () => {
  const candidates = [
    candidate('a', 0, 36), candidate('b', 240, 38), candidate('c', 720, 46),
  ]
  const learned = {
    ...profile,
    comparisons: 14,
    learning_confidence: .85,
    feature_weights: { syncopation: 7, register: -3 },
    preferred_ranges: {
      syncopation: {
        mean: .45, low: .35, high: .55, uncertainty: .1, observations: 9, evidence: .9,
      },
    },
  } as BassPreferenceSummary
  const first = buildBassPreferencePairPlans(candidates, profile)[0]
  const expectedNext = buildBassPreferencePairPlans(candidates, learned)
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
    <BassTasteTrainer candidates={candidates} preference={profile} onPreference={onPreference}/>,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Bass比較候補 1 を再生' }))
  await waitFor(() => expect(mocks.toggleBassPreview).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('button', { name: 'Bass比較候補 2 を再生' }))
  await waitFor(() => expect(mocks.toggleBassPreview).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: '候補 1 が支える' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

  view.rerender(
    <BassTasteTrainer candidates={candidates} preference={learned} onPreference={onPreference}/>,
  )
  fireEvent.click(screen.getByRole('button', { name: '次の組み合わせ' }))
  expect(screen.getByText(/比較 2\/3/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Bass比較候補 1 を再生' }))
  await waitFor(() => expect(mocks.toggleBassPreview).toHaveBeenCalledTimes(3))
  fireEvent.click(screen.getByRole('button', { name: 'Bass比較候補 2 を再生' }))
  await waitFor(() => expect(mocks.toggleBassPreview).toHaveBeenCalledTimes(4))
  fireEvent.click(screen.getByRole('button', { name: '差がない' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

  const secondBody = JSON.parse(String(fetchMock.mock.calls[1][1]?.body))
  expect([secondBody.candidate_a.pattern_id, secondBody.candidate_b.pattern_id].sort()).toEqual(
    expectedNext?.pair.map(item => item.pattern_id).sort(),
  )
})
