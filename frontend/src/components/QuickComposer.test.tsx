import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { BassPattern, GroovePattern } from '../types/generated'
import { QuickComposer } from './QuickComposer'

const mocks = vi.hoisted(() => ({
  generate: vi.fn(),
  jointGenerate: vi.fn(),
  groovePresets: vi.fn(),
  bassPresets: vi.fn(),
}))

vi.mock('../api/client', () => ({
  api: { generate: mocks.generate, presets: mocks.groovePresets },
  bassApi: {
    jointGenerate: mocks.jointGenerate,
    presets: mocks.bassPresets,
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
  mocks.groovePresets.mockResolvedValue({ built_in: { Balanced: {} }, user: {} })
  mocks.bassPresets.mockResolvedValue({ built_in: { Supportive: {} }, user: {} })
  const groove = { pattern_id: 'groove-warm' } as GroovePattern
  const bass = { pattern_id: 'bass-warm' } as BassPattern
  mocks.generate.mockResolvedValue({ candidates: [groove] })
  mocks.jointGenerate.mockResolvedValue({
    candidates: [{ groove_pattern: groove, bass_pattern: bass }],
  })
})

it('passes the selected drum sound into easy-mode generation', async () => {
  const onReady = vi.fn()
  render(<QuickComposer groove={null} bass={null} onReady={onReady} onOpenDetails={vi.fn()} />)
  fireEvent.click(await screen.findByRole('radio', { name: 'Warm Pocket · 柔らかく太い' }))
  fireEvent.click(screen.getByRole('button', { name: 'まとめて作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalled())
  expect(mocks.generate.mock.calls[0][0].render_profile).toBe('warm-pocket-v1')
  await waitFor(() => expect(onReady).toHaveBeenCalled())
})

it('forwards a selected genre style and its preset intent', async () => {
  const houseIntent = { target_dna: { density: .68 } }
  mocks.groovePresets.mockResolvedValue({
    built_in: { Balanced: {}, House: houseIntent },
    user: {},
  })
  render(<QuickComposer groove={null} bass={null} onReady={vi.fn()} onOpenDetails={vi.fn()} />)
  fireEvent.change(await screen.findByLabelText('Grooveのスタイル'), {
    target: { value: 'House' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'まとめて作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalled())
  expect(mocks.generate.mock.calls[0][0]).toMatchObject({
    preset: 'House',
    intent: houseIntent,
  })
})
