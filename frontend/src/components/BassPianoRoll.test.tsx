import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { BassPattern } from '../types/generated'
import { BassPianoRoll } from './BassPianoRoll'

const pattern = {
  pattern_id: 'bass-test', name: 'Bass test', bpm: 100, bars: 2,
  meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
  register_limits: { lowest_midi_note: 36, highest_midi_note: 48, preferred_center: 42, preferred_zone: 'core', max_single_leap: 12 },
  events: [{ event_id: 'note-1', grid_tick: 0, structural_offset_tick: 0, micro_offset_us: 0, duration_tick: 480, pitch: 36, velocity: 92, harmonic_role: 'root', rhythmic_role: 'anchor', articulation: { connection: 'normal', technique: 'normal', accent: 'normal', legato_overlap_tick: 0 }, structural_weight: .9, phrase_id: 'phrase-0', motif_id: 'motif-0', approach_target_id: null, locks: { timing: false, pitch: false, duration: false, velocity: false, articulation: false }, provenance: { origin: 'generated', generator_stage: 'performance', mutation_operation: null, parent_motif_id: 'motif-0' }, decision_trace: { onset_reason: 'Anchor on a strong beat.', pitch_reason: 'C2 functions as root.', duration_reason: '480 ticks preserves space.', octave_reason: 'C2 is below center.', articulation_reason: 'Normal connection at velocity 92.', kick_relationship: 'independent', target_event_id: null, target_pitch: null, factors: { metric_gravity: 1, structural_weight: .9 } } }],
  structural_events: [], analysis: null, groove_context: null,
} as unknown as BassPattern

describe('BassPianoRoll', () => {
  it('shows functional notes and supports bar selection', () => {
    const onSelect = vi.fn(); const onBars = vi.fn()
    render(<BassPianoRoll pattern={pattern} selected={null} selectedBars={new Set()} onSelect={onSelect} onBars={onBars} onChange={vi.fn()} />)
    fireEvent.click(screen.getByTitle('root · anchor'))
    expect(onSelect).toHaveBeenCalledWith(pattern.events[0])
    fireEvent.click(screen.getByText('BAR 2'))
    expect(onBars).toHaveBeenCalledWith(new Set([1]))
    expect(screen.getByText(/No kick context/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'STRUCTURE' }))
    expect(screen.getByRole('button', { name: 'STRUCTURE' }).className).toContain('active')
  })

  it('edits and locks the selected note without mutating the source', () => {
    const onChange = vi.fn()
    render(<BassPianoRoll pattern={pattern} selected={pattern.events[0]} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('GRID TICK'), { target: { value: '960' } })
    expect(onChange.mock.calls[0][0].events[0].grid_tick).toBe(960)
    fireEvent.change(screen.getByLabelText('PITCH'), { target: { value: '38' } })
    expect(onChange.mock.calls[1][0].events[0].pitch).toBe(38)
    fireEvent.click(screen.getByText('◇ PITCH'))
    expect(onChange.mock.calls[2][0].events[0].locks.pitch).toBe(true)
    fireEvent.click(screen.getByText('◇ DUR'))
    expect(onChange.mock.calls[3][0].events[0].locks.duration).toBe(true)
    fireEvent.click(screen.getByText('◇ VEL'))
    expect(onChange.mock.calls[4][0].events[0].locks.velocity).toBe(true)
    fireEvent.click(screen.getByText('◇ ART'))
    expect(onChange.mock.calls[5][0].events[0].locks.articulation).toBe(true)
    expect(pattern.events[0].pitch).toBe(36)
  })

  it('clamps structural offset and edits legato overlap', () => {
    const onChange = vi.fn()
    render(<BassPianoRoll pattern={pattern} selected={pattern.events[0]} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('STRUCTURAL OFFSET'), { target: { value: '-999' } })
    expect((onChange.mock.calls[0][0] as BassPattern).events[0].structural_offset_tick).toBeGreaterThanOrEqual(0)
    fireEvent.change(screen.getByLabelText('LEGATO OVERLAP'), { target: { value: '240' } })
    expect((onChange.mock.calls[1][0] as BassPattern).events[0].articulation.legato_overlap_tick).toBe(240)
  })

  it('clamps manual values to the canonical pattern and MIDI ranges', () => {
    const onChange = vi.fn()
    render(<BassPianoRoll pattern={pattern} selected={pattern.events[0]} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('PITCH'), { target: { value: '127' } })
    fireEvent.change(screen.getByLabelText('VELOCITY'), { target: { value: '999' } })
    fireEvent.change(screen.getByLabelText('MICRO µs'), { target: { value: '-99999' } })
    fireEvent.change(screen.getByLabelText('DURATION'), { target: { value: '999999' } })
    expect((onChange.mock.calls[0][0] as BassPattern).events[0].pitch).toBe(48)
    expect((onChange.mock.calls[1][0] as BassPattern).events[0].velocity).toBe(127)
    expect((onChange.mock.calls[2][0] as BassPattern).events[0].micro_offset_us).toBe(-25000)
    expect((onChange.mock.calls[3][0] as BassPattern).events[0].duration_tick).toBe(7680)
  })

  it('clears structural references when deleting their target note', () => {
    const onChange = vi.fn()
    const targeted = { ...pattern, structural_events: [{ event_id: 'gap-1', start_tick: 0, duration_tick: 240, role: 'recovery_target', target_event_id: 'note-1', strength: .8 }] } as BassPattern
    render(<BassPianoRoll pattern={targeted} selected={targeted.events[0]} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'DELETE' }))
    const next = onChange.mock.calls[0][0] as BassPattern
    expect(next.events).toHaveLength(0)
    expect(next.structural_events[0].target_event_id).toBeNull()
  })

  it('edits articulation details through the note inspector', () => {
    const onChange = vi.fn()
    render(<BassPianoRoll pattern={pattern} selected={pattern.events[0]} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('CONNECTION'), { target: { value: 'staccato' } })
    fireEvent.change(screen.getByLabelText('TECHNIQUE'), { target: { value: 'mute' } })
    fireEvent.change(screen.getByLabelText('ACCENT'), { target: { value: 'accent' } })
    expect((onChange.mock.calls[0][0] as BassPattern).events[0].articulation.connection).toBe('staccato')
    expect((onChange.mock.calls[1][0] as BassPattern).events[0].articulation.technique).toBe('mute')
    const next = onChange.mock.calls[2][0] as BassPattern
    expect(next.events[0].articulation.accent).toBe('accent')
    expect(next.events[0].provenance.origin).toBe('user_edited')
  })

  it('opens the structured generation trace for a selected note', () => {
    render(<BassPianoRoll pattern={pattern} selected={pattern.events[0]} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('TRACE'))
    expect(screen.getByText('WHY THIS ONSET?')).toBeTruthy()
    expect(screen.getByText('Anchor on a strong beat.')).toBeTruthy()
    expect(screen.getByText(/metric gravity/i)).toBeTruthy()
  })

  it('renders structural events in the optional preview strip', () => {
    const structured = { ...pattern, structural_events: [{ event_id: 'structure-1', start_tick: 960, duration_tick: 480, role: 'phrase_break', target_event_id: null, strength: .8 }] } as BassPattern
    render(<BassPianoRoll pattern={structured} selected={null} selectedBars={new Set()} onSelect={vi.fn()} onBars={vi.fn()} onChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'STRUCTURE' }))
    expect(screen.getByTitle('phrase break')).toBeTruthy()
  })
})
