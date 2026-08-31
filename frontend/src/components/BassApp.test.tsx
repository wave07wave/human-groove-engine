import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { BassIntent, BassPattern, GroovePattern } from '../types/generated'
import { replaceCandidateRevision } from '../utils/candidates'
import { BassApp } from './BassApp'

const intent = {
  target: { root_strength: .8, chord_tone_strength: .8, chromaticism: .1, approach_activity: .2, melodic_motion: .3, stepwise_motion: .7, leap_activity: .2, register_motion: .2, syncopation: .3, kick_lock: .6, kick_complement: .3, kick_answer: .2, density: .4, silence: .3, duration_contrast: .3, velocity_contrast: .3, repetition: .7, variation: .3, phrase_development: .4, tension: .3, resolution_strength: .7, human_feel: .3 },
  tolerances: { default: .14, per_dimension: {} }, priorities: { rhythm: 1, harmony: 1, melody: 1, kick_relation: 1, articulation: 1, phrase: 1 }, allow_chromatic_notes: true,
} as BassIntent
const groove = {
  pattern_id: 'groove-shared', name: 'Shared groove', bpm: 112, bars: 4,
  meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
  events: [{ instrument: 'kick' }],
} as unknown as GroovePattern
const context = {
  tempo_map: { segments: [{ start_tick: 0, bpm: 112 }] }, meter: groove.meter,
  phrase_boundaries: [0], beat_map: [], metric_gravity: [], tension_curve: [],
  kick_events: [{ grid_tick: 0, structural_offset_tick: 0, micro_offset_us: 0, velocity: 100 }], groove_dna: {},
}

function bassPattern(patternId: string): BassPattern {
  return {
    pattern_id: patternId, name: patternId, bpm: 112, bars: 4, meter: groove.meter,
    tempo_map: context.tempo_map, harmony: { events: [] }, key_context: null,
    input_mode: 'chord_progression', events: [], structural_events: [], intent,
    intent_locks: {}, register_limits: { lowest_midi_note: 28, highest_midi_note: 60, preferred_center: 42, preferred_zone: 'core', max_single_leap: 12 },
    voice_policy: 'monophonic_retrigger', metadata: { engine_version: '0.1', analysis_version: '0.1', schema_version: '1.0', preset_version: '1.0', master_seed: 42 },
    analysis: null, groove_context: context, interaction_analysis: null,
  } as unknown as BassPattern
}

afterEach(() => vi.unstubAllGlobals())

it('replaces the previous candidate when mutation creates a revision id', () => {
  const previous = { pattern_id: 'bass-1' } as BassPattern
  const other = { pattern_id: 'bass-2' } as BassPattern
  const revision = { pattern_id: 'bass-1-r1' } as BassPattern
  expect(replaceCandidateRevision([previous, other], revision, previous.pattern_id)).toEqual([revision, other])
})

it('links the selected Groove pattern and exposes every preview mode', async () => {
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    const body = url.includes('/context/from-groove') ? context : { built_in: { Supportive: intent }, user: {} }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  }))
  render(<BassApp groovePattern={groove} />)
  const link = await screen.findByRole('button', { name: 'LINK CURRENT GROOVE' })
  expect((link as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(link)
  await waitFor(() => expect(screen.getByRole('button', { name: '✓ GROOVE CONTEXT LINKED' })).toBeTruthy())
  const preview = screen.getByDisplayValue('Bass Only')
  expect(preview.querySelectorAll('option')).toHaveLength(5)
  expect(screen.getByLabelText('VOICE POLICY')).toBeTruthy()
  expect(screen.getByLabelText('MIDI CHANNEL')).toBeTruthy()
  expect(screen.getByText(/1 kicks/)).toBeTruthy()
})

it('marks a candidate created by preference-guided search', async () => {
  const guided = bassPattern('guided-bass')
  guided.metadata.preference_guided = true
  guided.metadata.preference_guidance_strength = .35
  guided.metadata.preference_guided_features = ['density']
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url === '/api/v1/bass/generate') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ candidates: [guided] }) })
    }
    if (url.includes('/history/generations') || url.endsWith('/patterns')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    }
    if (url.includes('/preferences')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(null) })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ built_in: { Supportive: intent }, user: {} }) })
  }))

  render(<BassApp groovePattern={null} />)
  fireEvent.click(await screen.findByRole('button', { name: 'GENERATE BASS' }))

  expect(await screen.findByText('好み探索 · 0 notes')).toBeTruthy()
})

it('applies the matching Groove when a Joint Candidate is selected', async () => {
  const firstGroove = { ...groove, pattern_id: 'joint-groove-a' }
  const secondGroove = { ...groove, pattern_id: 'joint-groove-b' }
  const firstBass = bassPattern('joint-bass-a')
  const secondBass = bassPattern('joint-bass-b')
  const jointResponse = {
    mode: 'negotiate', candidates: [
      { groove_pattern: firstGroove, bass_pattern: firstBass, interaction: {}, joint_fitness: .8, complexity_fit: .7, change_cost: .05, changes: [{ target: 'kick_lane', event_id: 'kick-1', operation: 'move', tick_before: 0, tick_after: 120, reason: 'improves lock' }] },
      { groove_pattern: secondGroove, bass_pattern: secondBass, interaction: {}, joint_fitness: .7, complexity_fit: .6, change_cost: 0, changes: [] },
    ],
  }
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url === '/api/v1/interaction/generate') return Promise.resolve({ ok: true, json: () => Promise.resolve(jointResponse) })
    if (url.includes('/history/generations') || url.endsWith('/patterns')) return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    if (url.includes('/preferences')) return Promise.resolve({ ok: true, json: () => Promise.resolve(null) })
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ built_in: { Supportive: intent }, user: {} }) })
  }))
  const onGrooveUpdate = vi.fn()
  render(<BassApp groovePattern={groove} onGrooveUpdate={onGrooveUpdate} />)

  fireEvent.change(await screen.findByDisplayValue('FOLLOW · Drums fixed'), { target: { value: 'negotiate' } })
  fireEvent.click(screen.getByRole('button', { name: 'GENERATE BASS' }))
  await screen.findByText('improves lock')
  expect(onGrooveUpdate).toHaveBeenLastCalledWith(firstGroove)
  expect(screen.getByLabelText('Joint changes').textContent).toContain('0 → 120 ticks')

  fireEvent.click(screen.getByRole('button', { name: /^B.*試聴候補/ }))
  await waitFor(() => expect(onGrooveUpdate).toHaveBeenLastCalledWith(secondGroove))
})

it('keeps an externally supplied Bass pattern instead of clearing the shared selection', async () => {
  const external = bassPattern('easy-mode-bass')
  external.bpm = 124
  external.bars = 2
  external.voice_policy = 'allow_overlap'
  external.metadata = { ...external.metadata, preset: 'Supportive' }
  const onBassPatternChange = vi.fn()
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url === '/api/v1/bass/evaluate') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(external) })
    }
    if (url.includes('/patterns') || url.includes('/history/generations')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
    }
    if (url.includes('/preferences')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(null) })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ built_in: { Supportive: intent }, user: {} }) })
  }))

  render(
    <BassApp
      groovePattern={groove}
      externalPattern={external}
      onBassPatternChange={onBassPatternChange}
    />,
  )

  await waitFor(() => expect(onBassPatternChange).toHaveBeenCalledWith(external))
  expect(onBassPatternChange).not.toHaveBeenCalledWith(null)
  expect((screen.getByLabelText('BPM') as HTMLInputElement).value).toBe('124')
  expect((screen.getByLabelText('BARS') as HTMLSelectElement).value).toBe('2')
  expect((screen.getByLabelText('VOICE POLICY') as HTMLSelectElement).value).toBe('allow_overlap')
})
