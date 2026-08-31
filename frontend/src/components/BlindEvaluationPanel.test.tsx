import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { GenerateRequest, GroovePattern } from '../types/generated'
import { BlindEvaluationPanel } from './BlindEvaluationPanel'

const mocks = vi.hoisted(() => ({
  togglePreview: vi.fn(async (_pattern, onState: (value: boolean) => void) => onState(true)),
}))

vi.mock('../audio/preview', () => ({ togglePreview: mocks.togglePreview }))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it('requires explicit consent before a blind comparison starts', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
  render(<BlindEvaluationPanel generation={{} as GenerateRequest}/>)

  const start = screen.getByRole('button', { name: '6回の比較を始める' }) as HTMLButtonElement
  expect(start.disabled).toBe(true)
  fireEvent.click(screen.getByRole('checkbox'))
  expect(start.disabled).toBe(false)
  expect(screen.queryByText(/学習済み演奏/)).toBeNull()
})

it('freezes the generation settings for all six trials', async () => {
  const generation = { bpm: 100, bars: 2, seed: 40, candidate_count: 1 } as GenerateRequest
  const pattern = { pattern_id: 'blind-pattern', events: [] } as unknown as GroovePattern
  const sessionRequests: Record<string, unknown>[] = []
  const summary = {
    completed: 0, groups: [], minimum_blocks_per_declared_group: 20,
    verdict: 'collecting', perceptual_claim_allowed: false,
    eligible_repeat_pairs: 0, repeat_consistency: null, caveat: 'test',
  }
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    if (url === '/api/v1/evaluation/summary') return Promise.resolve({ ok: true, json: async () => summary } as Response)
    if (url === '/api/v1/evaluation/sessions') {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      sessionRequests.push(body)
      return Promise.resolve({ ok: true, json: async () => ({
        session_id: `session-${sessionRequests.length}`,
        participant_group: 'undisclosed',
        started_at: new Date().toISOString(),
        study_run_id: body.study_run_id,
        trial_index: body.trial_index,
        trials_in_block: 6,
        candidates: [{ position: 'left', pattern }, { position: 'right', pattern: { ...pattern, pattern_id: 'blind-pattern-right' } }],
        instructions: 'test',
      }) } as Response)
    }
    if (url === '/api/v1/evaluation/responses') return Promise.resolve({ ok: true, json: async () => ({ accepted: true, selected_variant: 'tie', left_variant: 'learned', right_variant: 'rule' }) } as Response)
    return new Promise(() => undefined)
  })
  vi.stubGlobal('fetch', fetchMock)

  const view = render(<BlindEvaluationPanel generation={generation}/>)
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: '6回の比較を始める' }))
  await screen.findByText(/試行 1\/6/)
  const playButtons = screen.getAllByRole('button', { name: '▶ 再生' })
  fireEvent.click(playButtons[0]); fireEvent.click(playButtons[1])
  await waitFor(() => expect((screen.getByRole('button', { name: '同じくらい' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '同じくらい' }))
  await screen.findByText('回答を記録しました')

  view.rerender(<BlindEvaluationPanel generation={{ ...generation, bpm: 180, seed: 900 }}/>)
  fireEvent.click(screen.getByRole('button', { name: '次の比較' }))
  await waitFor(() => expect(sessionRequests).toHaveLength(2))
  const secondGeneration = sessionRequests[1].generation as GenerateRequest
  expect(secondGeneration.bpm).toBe(100)
  expect(secondGeneration.seed).toBe(41)
})
