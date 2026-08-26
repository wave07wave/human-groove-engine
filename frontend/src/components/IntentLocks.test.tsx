import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { EMPTY_INTENT_LOCKS } from '../utils/intentLocks'
import { IntentLocks } from './IntentLocks'

it('toggles a durable Intent Lock', () => {
  const onChange = vi.fn()
  render(<IntentLocks value={EMPTY_INTENT_LOCKS} onChange={onChange} />)

  fireEvent.click(screen.getByLabelText('Register'))

  expect(onChange).toHaveBeenCalledWith({ ...EMPTY_INTENT_LOCKS, keep_register: true })
})
