import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { GrooveIntent, GroovePattern } from './types/generated'
import App from './App'

afterEach(() => vi.unstubAllGlobals())

it('switches between Groove and Bass engines', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
  render(<App />)
  expect(screen.getByText('少しの揺らぎが、Grooveを生む。')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'BASS' }))
  expect(screen.getByText('支え、動き、導き、解決する。')).toBeTruthy()
})

it('offers an easy workspace alongside the detailed editors', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'かんたん' }))
  expect(screen.getByText('少ない設定で、すぐに一曲の土台を。')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'まとめて作成' })).toBeTruthy()
})

it('passes the generated Groove candidate into the Bass context link flow', async () => {
  const intent = {
    target_dna: { pulse_stability: .7, syncopation: .4, surprise: .3, motor_affordance: .7, microtiming: .2, variation: .3, metric_ambiguity: .2, density: .5 },
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
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url === '/api/v1/presets') return Promise.resolve({ ok: true, json: () => Promise.resolve({ built_in: { Balanced: intent }, user: {} }) })
    if (url === '/api/v1/generate') return Promise.resolve({ ok: true, json: () => Promise.resolve({ candidates: [groove] }) })
    if (url.includes('/context/from-groove')) return Promise.resolve({ ok: true, json: () => Promise.resolve(context) })
    return new Promise(() => undefined)
  }))

  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Grooveを作成' }))
  await screen.findByText('Shared integration groove')
  fireEvent.click(screen.getByRole('button', { name: 'BASS' }))
  const link = screen.getByRole('button', { name: 'LINK CURRENT GROOVE' })
  expect((link as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(link)
  await waitFor(() => expect(screen.getByRole('button', { name: '✓ GROOVE CONTEXT LINKED' })).toBeTruthy())
})
