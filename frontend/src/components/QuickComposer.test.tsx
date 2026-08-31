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
  expect(mocks.generate.mock.calls[0][0].preset).toBe('House')
  expect(mocks.generate.mock.calls[0][0].intent.target_dna.density).toBeCloseTo(.72)
})

it('lets the player choose a bolder generation width', async () => {
  const onReady = vi.fn()
  mocks.groovePresets.mockResolvedValue({
    built_in: { Balanced: { target_dna: { variation: .35, surprise: .35 } } }, user: {},
  })
  render(<QuickComposer groove={null} bass={null} onReady={onReady} onOpenDetails={vi.fn()} />)
  fireEvent.change(await screen.findByLabelText('パターンの幅'), { target: { value: 'adventurous' } })
  fireEvent.click(screen.getByRole('button', { name: 'まとめて作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalled())
  expect(mocks.generate.mock.calls[0][0].intent.target_dna).toMatchObject({ variation: .63, surprise: .55 })
  expect(mocks.generate.mock.calls[0][0].candidate_strategy).toBe('explore')
})

it('carries an adventurous width into Bass phrasing and the joint complexity budget', async () => {
  mocks.bassPresets.mockResolvedValue({
    built_in: {
      Supportive: {
        target: {
          variation: .3,
          phrase_development: .4,
          syncopation: .3,
          melodic_motion: .3,
          density: .4,
          silence: .3,
        },
      },
    },
    user: {},
  })
  render(<QuickComposer groove={null} bass={null} onReady={vi.fn()} onOpenDetails={vi.fn()} />)

  fireEvent.change(await screen.findByLabelText('パターンの幅'), {
    target: { value: 'adventurous' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'まとめて作成' }))

  await waitFor(() => expect(mocks.jointGenerate).toHaveBeenCalledTimes(1))
  const [, bassRequest, mode, complexityBudget, bassShare] = mocks.jointGenerate.mock.calls[0]
  expect(bassRequest.intent.target.variation).toBeCloseTo(.54)
  expect(bassRequest.intent.target.phrase_development).toBeCloseTo(.6)
  expect(bassRequest.intent.target.syncopation).toBeCloseTo(.44)
  expect(bassRequest.intent.target.melodic_motion).toBeCloseTo(.42)
  expect(bassRequest.intent.target.density).toBeCloseTo(.48)
  expect(bassRequest.intent.target.silence).toBeCloseTo(.24)
  expect(mode).toBe('follow')
  expect(complexityBudget).toBe(.78)
  expect(bassShare).toBe(.67)
})
