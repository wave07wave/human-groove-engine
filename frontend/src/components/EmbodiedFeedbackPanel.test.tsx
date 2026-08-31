import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'

import { EmbodiedFeedbackPanel } from './EmbodiedFeedbackPanel'

const mocks = vi.hoisted(() => ({
  embodiedEvaluationSummary: vi.fn(),
}))

vi.mock('../api/client', () => ({
  api: {
    embodiedEvaluationSummary: mocks.embodiedEvaluationSummary,
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

it('renders a partial evaluation summary without assuming operator arms are present', async () => {
  mocks.embodiedEvaluationSummary.mockResolvedValue({
    total_evaluations: 0,
    minimum_evaluations_per_arm: 3,
    sufficient_for_personal_comparison: false,
  })

  render(<EmbodiedFeedbackPanel pattern={{} as never} />)

  expect(await screen.findByText('あなたの評価傾向 · 0件')).toBeTruthy()
  expect(screen.getByText('各アーム3件以上で比較の目安になります。')).toBeTruthy()
})
