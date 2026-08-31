import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { GroovePattern } from '../types/generated'
import { StepGrid } from './StepGrid'

const pattern = {
  pattern_id:'test',name:'Test groove',bpm:100,bars:1,
  meter:{numerator:4,denominator:4,grouping:[2,2],subdivisions_per_quarter:4},
  events:[],instrument_locks:[],bar_locks:[],analysis:null,
  intent:{target_dna:{},tolerance:{default:.1,per_dimension:{}},priorities:{weights:{}},movement_target:'bounce'},
  metadata:{engine_version:'1',analysis_version:'1',schema_version:'1',preset_version:'1',rng_algorithm:'PCG64DXSM',master_seed:1},
} as unknown as GroovePattern

describe('StepGrid', () => {
  it('supports grid editing and instrument locks', () => {
    const onToggle = vi.fn(); const onLock = vi.fn()
    render(<StepGrid pattern={pattern} selectedBars={new Set()} selectedInstrument={null} onToggle={onToggle} onSelectEvent={vi.fn()} onSelectBar={vi.fn()} onSelectInstrument={vi.fn()} onLockInstrument={onLock}/>)
    fireEvent.click(screen.getByLabelText('kick step 1'))
    expect(onToggle).toHaveBeenCalledWith('kick', 0)
    fireEvent.click(screen.getAllByTitle('Instrument lock')[0])
    expect(onLock).toHaveBeenCalledWith('kick')
    expect(screen.getAllByRole('button', { name: /step/ })).toHaveLength(96)
  })

  it('renders ten sixteenth steps per bar in 5/8', () => {
    const fiveEight = {
      ...pattern,
      meter: { numerator: 5, denominator: 8, grouping: [3, 2], subdivisions_per_quarter: 4 },
    }
    render(<StepGrid pattern={fiveEight} selectedBars={new Set()} selectedInstrument={null} onToggle={vi.fn()} onSelectEvent={vi.fn()} onSelectBar={vi.fn()} onSelectInstrument={vi.fn()} onLockInstrument={vi.fn()}/>)
    expect(screen.getAllByRole('button', { name: /step/ })).toHaveLength(60)
  })

  it('edits an eighth-note triplet grid at exact 320 tick positions', () => {
    const triplet = { ...pattern, meter: { ...pattern.meter, subdivisions_per_quarter: 3 } }
    const onToggle = vi.fn()
    render(<StepGrid pattern={triplet} selectedBars={new Set()} selectedInstrument={null} onToggle={onToggle} onSelectEvent={vi.fn()} onSelectBar={vi.fn()} onSelectInstrument={vi.fn()} onLockInstrument={vi.fn()}/>)
    expect(screen.getAllByRole('button', { name: /step/ })).toHaveLength(72)
    fireEvent.click(screen.getByLabelText('kick step 2'))
    expect(onToggle).toHaveBeenCalledWith('kick', 320)
    expect(screen.getByText(/8分3連/)).toBeTruthy()
  })

  it('renders a complete thirty-second-note grid', () => {
    const thirtySecond = { ...pattern, meter: { ...pattern.meter, subdivisions_per_quarter: 8 } }
    render(<StepGrid pattern={thirtySecond} selectedBars={new Set()} selectedInstrument={null} onToggle={vi.fn()} onSelectEvent={vi.fn()} onSelectBar={vi.fn()} onSelectInstrument={vi.fn()} onLockInstrument={vi.fn()}/>)
    expect(screen.getAllByRole('button', { name: /step/ })).toHaveLength(192)
  })
})
