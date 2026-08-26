import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { parseHarmonyPlan, serializeHarmonyPlan } from '../utils/harmonyPlan'
import { HarmonyEditor } from './HarmonyEditor'

it('round-trips chord quality, slash bass and adjacent duration', () => {
  const plan = parseHarmonyPlan('Dm7 | Dm7 | G7/B')
  expect(plan).not.toBeNull()
  expect(plan?.[0]).toEqual({ root: 'D', quality: 'm7', slashBass: '', durationBars: 2 })
  expect(plan?.[1].slashBass).toBe('B')
  expect(serializeHarmonyPlan(plan ?? [])).toBe('Dm7 | Dm7 | G7/B')
})

it('edits duration and renders the output-bar timeline', () => {
  const onChange = vi.fn()
  render(<HarmonyEditor value="Dm7 | G7" bars={4} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('DURATION 1'), { target: { value: '3' } })
  expect(onChange).toHaveBeenCalledWith('Dm7 | Dm7 | Dm7 | G7')
  expect(screen.getByText('BAR 4')).toBeTruthy()
})

it('edits root, quality and slash bass with supported symbols', () => {
  const rootChange = vi.fn()
  const { unmount } = render(<HarmonyEditor value="C" bars={1} onChange={rootChange} />)
  fireEvent.change(screen.getByLabelText('ROOT 1'), { target: { value: 'F#' } })
  expect(rootChange).toHaveBeenCalledWith('F#')
  unmount()

  const chordChange = vi.fn()
  render(<HarmonyEditor value="F#" bars={1} onChange={chordChange} />)
  fireEvent.change(screen.getByLabelText('QUALITY 1'), { target: { value: 'm7b5' } })
  expect(chordChange).toHaveBeenCalledWith('F#m7b5')
  fireEvent.change(screen.getByLabelText('SLASH BASS 1'), { target: { value: 'A' } })
  expect(chordChange).toHaveBeenCalledWith('F#/A')
})
