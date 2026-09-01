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

it('offers every Detroit Soul drummer choice and sends the selected profile', async () => {
  render(<QuickComposer groove={null} bass={null} onReady={vi.fn()} onOpenDetails={vi.fn()} />)
  const drummer = await screen.findByLabelText('Detroit Soul ドラマー') as HTMLSelectElement

  expect(Array.from(drummer.options).map(option => option.value)).toEqual([
    'standard', 'benny', 'pistol', 'uriel', 'blend',
  ])
  fireEvent.change(drummer, { target: { value: 'uriel' } })
  expect(screen.getByText(/広い間、ゴーストノート、強い一打/)).toBeTruthy()
  expect(screen.getByText(/本人の演奏の完全な再現/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'まとめて作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalledTimes(1))
  expect(mocks.generate.mock.calls[0][0].detroit_soul).toEqual({
    mode: 'uriel',
    blend: { benny: 1 / 3, pistol: 1 / 3, uriel: 1 / 3 },
  })
})

it('keeps an existing detailed blend when returning to easy mode', async () => {
  const blend = { benny: .55, pistol: .3, uriel: .15 }
  const existing = {
    pattern_id: 'existing-detroit-blend',
    metadata: { detroit_soul: { mode: 'blend', blend } },
  } as GroovePattern
  render(<QuickComposer groove={existing} bass={null} onReady={vi.fn()} onOpenDetails={vi.fn()} />)

  expect((await screen.findByLabelText('Detroit Soul ドラマー') as HTMLSelectElement).value).toBe('blend')
  fireEvent.click(screen.getByRole('button', { name: 'まとめて作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalledTimes(1))
  expect(mocks.generate.mock.calls[0][0].detroit_soul).toEqual({ mode: 'blend', blend })
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
