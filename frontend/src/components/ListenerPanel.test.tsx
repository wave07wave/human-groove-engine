import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import type { GrooveAnalysis } from '../types/generated'
import { ListenerPanel } from './ListenerPanel'

it('labels listener values as model predictions', () => {
  const analysis = { listener:{predicted_groove:.82,beat_confidence:.91,meter_confidence:.8,movement_proxy:.87,pleasure_proxy:.7,surprise:.54,resolvable_surprise:.65,learning_progress:.42,boredom:.12,confusion:.17,irritation:.08,confidence:.72},confidence:{overall:.72,caveat:'heuristic'},intent_loss:.1,fitness:.7,measured_dna:{} } as unknown as GrooveAnalysis
  render(<ListenerPanel analysis={analysis}/>)
  expect(screen.getByText('82')).toBeTruthy()
  expect(screen.getByText(/生理学的測定ではありません/)).toBeTruthy()
})
