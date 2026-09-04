import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { KeyboardPattern } from '../types/generated'
import { KeyboardApp } from './KeyboardApp'

const mocks = vi.hoisted(() => ({
  generate: vi.fn(),
  mutate: vi.fn(),
  patterns: vi.fn(),
  savePattern: vi.fn(),
  generationHistory: vi.fn(),
  generationPattern: vi.fn(),
  midi: vi.fn(),
}))

vi.mock('../api/client', () => ({
  keyboardApi: {
    ...mocks,
    deletePattern: vi.fn(),
    evaluate: vi.fn(),
    exportPattern: vi.fn(),
    importPattern: vi.fn(),
  },
}))

const pattern = {
  pattern_id: 'keys-joe-43',
  name: 'Generated Keys',
  bpm: 100,
  bars: 4,
  meter: { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
  harmony_text: 'Dm7 | G7 | Cmaj7 | A7',
  events: [],
  rhythm_context: { kick_ticks: [], snare_ticks: [], bass_ticks: [] },
  bar_locks: [],
  metadata: {
    detroit_keyboard: { mode: 'joe', blend: { earl: 1 / 3, joe: 1 / 3, johnny: 1 / 3 } },
  },
  analysis: null,
} as unknown as KeyboardPattern

beforeEach(() => {
  vi.clearAllMocks()
  mocks.patterns.mockResolvedValue([])
  mocks.generationHistory.mockResolvedValue([])
  mocks.generate.mockResolvedValue({ candidates: [pattern] })
})

it('generates the selected keyboardist style in the detailed Keys workspace', async () => {
  render(<KeyboardApp groovePattern={null} bassPattern={null} />)
  const style = screen.getByLabelText('Detroit Soul キーボード') as HTMLSelectElement

  expect(Array.from(style.options).map(option => option.value)).toEqual([
    'standard', 'earl', 'joe', 'johnny', 'blend',
  ])
  fireEvent.change(style, { target: { value: 'joe' } })
  fireEvent.click(screen.getByRole('button', { name: 'Keysを作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalledTimes(1))
  expect(mocks.generate.mock.calls[0][0]).toMatchObject({
    seed: 43,
    candidate_count: 4,
    detroit_keyboard: { mode: 'joe' },
    rhythm_context: { kick_ticks: [], snare_ticks: [], bass_ticks: [] },
  })
  expect(await screen.findByText('Generated Keys')).toBeTruthy()
})

it('shows and sends the three influence controls in blend mode', async () => {
  render(<KeyboardApp groovePattern={null} bassPattern={null} />)
  fireEvent.change(screen.getByLabelText('Detroit Soul キーボード'), { target: { value: 'blend' } })
  fireEvent.change(screen.getByLabelText('Earl の影響度'), { target: { value: '.6' } })
  fireEvent.change(screen.getByLabelText('Joe の影響度'), { target: { value: '.25' } })
  fireEvent.change(screen.getByLabelText('Johnny の影響度'), { target: { value: '.15' } })
  fireEvent.click(screen.getByRole('button', { name: 'Keysを作成' }))

  await waitFor(() => expect(mocks.generate).toHaveBeenCalledTimes(1))
  expect(mocks.generate.mock.calls[0][0].detroit_keyboard).toEqual({
    mode: 'blend', blend: { earl: .6, joe: .25, johnny: .15 },
  })
})

it('restores an easy-mode pattern without overwriting the next detailed generation', async () => {
  const external = {
    ...pattern,
    pattern_id: 'easy-keys',
    name: 'Easy Keys',
    metadata: { detroit_keyboard: { mode: 'earl', blend: { earl: 1, joe: 0, johnny: 0 } } },
  } as KeyboardPattern
  const generated = {
    ...pattern,
    pattern_id: 'detailed-keys',
    name: 'Detailed Keys',
    metadata: { detroit_keyboard: { mode: 'johnny', blend: { earl: 0, joe: 0, johnny: 1 } } },
  } as KeyboardPattern
  const onChange = vi.fn()
  mocks.generate.mockResolvedValue({ candidates: [generated] })
  render(<KeyboardApp groovePattern={null} bassPattern={null} externalPattern={external} onKeyboardPatternChange={onChange} />)

  expect(await screen.findByText('Easy Keys')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Detroit Soul キーボード'), { target: { value: 'johnny' } })
  fireEvent.click(screen.getByRole('button', { name: 'Keysを作成' }))

  expect(await screen.findByText('Detailed Keys')).toBeTruthy()
  await waitFor(() => expect(onChange).toHaveBeenLastCalledWith(generated))
})
