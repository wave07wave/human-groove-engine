import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { GrooveIntent, GroovePattern } from './types/generated'
import App from './App'

afterEach(() => vi.unstubAllGlobals())

it('switches between Groove, Bass, and Keys engines', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
  render(<App />)
  expect(screen.getByText('少しの揺らぎが、Grooveを生む。')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'BASS' }))
  expect(screen.getByText('支え、動き、導き、解決する。')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'KEYS' }))
  expect(screen.getByText('響き、支え、応答する。')).toBeTruthy()
})

it('offers an easy workspace alongside the detailed editors', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'かんたん' }))
  expect(screen.getByText('少ない設定で、すぐに一曲の土台を。')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'まとめて作成' })).toBeTruthy()
  const studio = screen.getByRole('radio', { name: 'Studio Tight · タイトで明瞭' })
  const warm = screen.getByRole('radio', { name: 'Warm Pocket · 柔らかく太い' })
  expect(studio.getAttribute('aria-checked')).toBe('true')
  fireEvent.click(warm)
  expect(warm.getAttribute('aria-checked')).toBe('true')
})

it('passes the generated Groove candidate into the Bass context link flow', async () => {
  const intent = {
    target_dna: {
      pulse_stability: .7, beat_salience: .7, syncopation: .4, anticipation: .3,
      omission: .2, density: .5, repetition: .7, variation: .3, interlock: .6,
      swing: .2, microtiming: .2, velocity_contrast: .4, duration_contrast: .3,
      low_end_anchor: .7, metric_ambiguity: .2, ghost_density: .2, surprise: .3,
      recovery_strength: .7, motor_affordance: .7, hypnotic: .4, phrase_development: .4,
    },
    tolerance: { default: .12, per_dimension: {} }, priorities: { weights: {} }, movement_target: 'bounce',
  } as unknown as GrooveIntent
  const groove = {
    pattern_id: 'shared-integration', name: 'Shared integration groove', bpm: 108, bars: 1,
    meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
    events: [{ event_id: 'kick-1', instrument: 'kick', grid_tick: 0, structural_offset_tick: 0, micro_offset_us: 0, duration_tick: 180, velocity: 100, pitch: 36, primary_role: 'anchor', role_tags: [], accent: .9, timbre_variant: null, duration_style: 'medium', choke_group: null, locked: false, origin: 'generated' }],
    intent, metadata: { engine_version: '0.1', analysis_version: '0.1', schema_version: '1.0', preset_version: '1.0', rng_algorithm: 'PCG64DXSM', master_seed: 42 },
    analysis: null, instrument_locks: [], bar_locks: [],
  } as unknown as GroovePattern
  const context = { tempo_map: { segments: [{ start_tick: 0, bpm: 108 }] }, meter: groove.meter, phrase_boundaries: [0], beat_map: [], metric_gravity: [], tension_curve: [], kick_events: [{ grid_tick: 0, structural_offset_tick: 0, micro_offset_us: 0, velocity: 100 }], groove_dna: {} }
  const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
    void _init
    const url = String(input)
    if (url === '/api/v1/presets') return Promise.resolve({ ok: true, json: () => Promise.resolve({ built_in: { Balanced: intent }, user: {} }) })
    if (url === '/api/v1/generate') return Promise.resolve({ ok: true, json: () => Promise.resolve({ candidates: [groove] }) })
    if (url === '/api/v1/evaluate') return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(String(_init?.body))) })
    if (url.includes('/context/from-groove')) return Promise.resolve({ ok: true, json: () => Promise.resolve(context) })
    return new Promise(() => undefined)
  })
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Grooveを作成' }))
  await screen.findByText('Shared integration groove')
  fireEvent.change(screen.getByLabelText('ドラム音色'), {
    target: { value: 'warm-pocket-v1' },
  })
  await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input) === '/api/v1/evaluate')).toBe(true))
  const evaluation = fetchMock.mock.calls.find(([input]) => String(input) === '/api/v1/evaluate')
  expect(JSON.parse(String(evaluation?.[1]?.body)).metadata.render_profile).toBe('warm-pocket-v1')
  fireEvent.click(screen.getByRole('button', { name: 'BASS' }))
  const link = screen.getByRole('button', { name: 'LINK CURRENT GROOVE' })
  expect((link as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(link)
  await waitFor(() => expect(screen.getByRole('button', { name: '✓ GROOVE CONTEXT LINKED' })).toBeTruthy())
}, 15_000)
