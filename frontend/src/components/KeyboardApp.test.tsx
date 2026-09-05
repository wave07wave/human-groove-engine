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
    master_seed: 43,
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
    metadata: {
      ...pattern.metadata,
      master_seed: 42,
      detroit_keyboard: { mode: 'earl', blend: { earl: 1, joe: 0, johnny: 0 } },
    },
  } as KeyboardPattern
  const generated = {
    ...pattern,
    pattern_id: 'detailed-keys',
    name: 'Detailed Keys',
    metadata: {
      ...pattern.metadata,
      master_seed: 43,
      detroit_keyboard: { mode: 'johnny', blend: { earl: 0, joe: 0, johnny: 1 } },
    },
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

it('keeps all generated candidates available after choosing candidate B', async () => {
  const candidates = Array.from({ length: 4 }, (_, index) => ({
    ...pattern,
    pattern_id: `keys-candidate-${index}`,
    name: `Candidate ${String.fromCharCode(65 + index)}`,
    metadata: { ...pattern.metadata, candidate_index: index },
  } as KeyboardPattern))
  mocks.generate.mockResolvedValue({ candidates })
  render(<KeyboardApp groovePattern={null} bassPattern={null} />)

  fireEvent.click(screen.getByRole('button', { name: 'Keysを作成' }))
  expect(await screen.findByText('Candidate A')).toBeTruthy()
  const candidateButtons = screen.getAllByRole('button', { name: /Keys候補/ })
  expect(candidateButtons).toHaveLength(4)
  expect(new Set(candidates.map(candidate => candidate.pattern_id)).size).toBe(4)

  fireEvent.click(candidateButtons[1])

  expect(await screen.findByText('Candidate B')).toBeTruthy()
  expect(screen.getAllByRole('button', { name: /Keys候補/ })).toHaveLength(4)
  expect(screen.getAllByRole('button', { name: /Keys候補/ })[1].getAttribute('aria-pressed')).toBe('true')
})

it('keeps a regenerated candidate in its original candidate slot', async () => {
  const candidates = Array.from({ length: 4 }, (_, index) => ({
    ...pattern,
    pattern_id: `keys-stream-${index}`,
    name: `Stream ${String.fromCharCode(65 + index)}`,
    metadata: { ...pattern.metadata, candidate_index: index },
  } as KeyboardPattern))
  const regenerated = {
    ...candidates[1],
    pattern_id: 'keys-stream-1-r1',
    name: 'Stream B regenerated',
  } as KeyboardPattern
  mocks.generate.mockResolvedValue({ candidates })
  mocks.mutate.mockResolvedValue(regenerated)
  render(<KeyboardApp groovePattern={null} bassPattern={null} />)

  fireEvent.click(screen.getByRole('button', { name: 'Keysを作成' }))
  expect(await screen.findByText('Stream A')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: /Keys候補/ })[1])
  expect(await screen.findByText('Stream B')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '↻ 全小節を再作成' }))

  expect(await screen.findByText('Stream B regenerated')).toBeTruthy()
  const buttons = screen.getAllByRole('button', { name: /Keys候補/ })
  expect(buttons).toHaveLength(4)
  expect(buttons[1].getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(buttons[0])
  expect(await screen.findByText('Stream A')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: /Keys候補/ })[2])
  expect(await screen.findByText('Stream C')).toBeTruthy()
})

it('keeps a successful generation when only the history refresh fails', async () => {
  render(<KeyboardApp groovePattern={null} bassPattern={null} />)
  await waitFor(() => expect(mocks.generationHistory).toHaveBeenCalledTimes(1))
  mocks.generationHistory.mockRejectedValueOnce(new Error('history offline'))

  fireEvent.click(screen.getByRole('button', { name: 'Keysを作成' }))

  expect(await screen.findByText('Generated Keys')).toBeTruthy()
  expect((await screen.findByText(
    'Keysは生成されましたが、履歴一覧を更新できませんでした。',
  )).textContent).toContain('Keysは生成されましたが、履歴一覧を更新できませんでした。')
  expect(screen.queryByText(/Keysを生成できませんでした/)).toBeNull()
})

it('reports a MIDI export failure without losing the current pattern', async () => {
  mocks.midi.mockRejectedValueOnce(new Error('download failed'))
  render(<KeyboardApp groovePattern={null} bassPattern={null} externalPattern={pattern} />)
  expect(await screen.findByText('Generated Keys')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: '↓ MIDI' }))

  expect((await screen.findByRole('alert')).textContent).toContain('MIDIを書き出せませんでした')
  expect(screen.getByText('Generated Keys')).toBeTruthy()
})

it('announces that changed controls have not altered the displayed pattern', async () => {
  const current = {
    ...pattern,
    metadata: {
      ...pattern.metadata,
      master_seed: 42,
      detroit_keyboard: { mode: 'standard', blend: { earl: 1 / 3, joe: 1 / 3, johnny: 1 / 3 } },
    },
  } as KeyboardPattern
  render(<KeyboardApp groovePattern={null} bassPattern={null} externalPattern={current} />)
  expect(await screen.findByText('Generated Keys')).toBeTruthy()
  await waitFor(() => expect(screen.queryByText(/設定が変わっています/)).toBeNull())

  fireEvent.change(screen.getByLabelText('Detroit Soul キーボード'), {
    target: { value: 'johnny' },
  })

  expect((await screen.findByRole('status')).textContent).toContain(
    '再生・保存・MIDIは現在表示中のパターンを使用します。',
  )
})

it('does not mark a standalone history pattern dirty only because it remembers rhythm context', async () => {
  const historical = {
    ...pattern,
    metadata: { ...pattern.metadata, master_seed: 77 },
    rhythm_context: { kick_ticks: [0, 960], snare_ticks: [960], bass_ticks: [0, 480] },
  } as KeyboardPattern
  render(<KeyboardApp groovePattern={null} bassPattern={null} externalPattern={historical} />)

  expect(await screen.findByText('Generated Keys')).toBeTruthy()
  await waitFor(() => expect((screen.getByLabelText('KEYS SEED') as HTMLInputElement).value).toBe('77'))
  expect(screen.queryByText(/設定が変わっています/)).toBeNull()
})
