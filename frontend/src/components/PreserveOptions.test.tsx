import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { EMPTY_PRESERVE_OPTIONS } from '../utils/preserveOptions'
import { PreserveOptions } from './PreserveOptions'

it('toggles each preservation dimension independently', () => {
  const onChange = vi.fn()
  render(<PreserveOptions value={EMPTY_PRESERVE_OPTIONS} onChange={onChange} />)

  fireEvent.click(screen.getByLabelText('Pitch'))

  expect(onChange).toHaveBeenCalledWith({ ...EMPTY_PRESERVE_OPTIONS, keep_pitch: true })
  expect(screen.getByText(/0 ACTIVE/)).toBeTruthy()
})
