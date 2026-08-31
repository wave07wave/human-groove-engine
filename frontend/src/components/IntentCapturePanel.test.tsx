import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { GrooveIntent } from '../types/generated'
import { IntentCapturePanel } from './IntentCapturePanel'

const intent = {
  target_dna: {},
  tolerance: { default: .12, per_dimension: {} },
  priorities: { weights: {} },
  movement_target: 'bounce',
  phrase_energy_curve: [.3, .58, .82, .38],
} as unknown as GrooveIntent

it('captures taps locally and applies an editable phrase energy curve', () => {
  const onApply = vi.fn()
  render(<IntentCapturePanel intent={intent} onApply={onApply}/>)
  const tap = screen.getByRole('button', { name: '● TAP' })
  fireEvent.click(tap); fireEvent.click(tap); fireEvent.click(tap)
  expect(screen.getByText('3 taps')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('energy point 3'), { target: { value: '.95' } })
  expect(onApply).toHaveBeenCalledWith(
    expect.objectContaining({ phrase_energy_curve: [.3, .58, .95, .38] }),
    expect.objectContaining({ notice: expect.stringContaining('エネルギー') }),
  )
})
