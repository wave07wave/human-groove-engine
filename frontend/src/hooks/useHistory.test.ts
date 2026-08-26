import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useHistory } from './useHistory'

describe('useHistory', () => {
  it('replaces server-derived state without adding an Undo step', () => {
    const { result } = renderHook(() => useHistory<{ value: number, analyzed: boolean }>(null))

    act(() => result.current.commit({ value: 1, analyzed: true }))
    act(() => result.current.commit({ value: 2, analyzed: false }))
    act(() => result.current.replace({ value: 2, analyzed: true }))

    expect(result.current.present).toEqual({ value: 2, analyzed: true })
    act(() => result.current.undo())
    expect(result.current.present).toEqual({ value: 1, analyzed: true })
  })
})
