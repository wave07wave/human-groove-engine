import { describe, expect, it } from 'vitest'
import {
  drumVelocityGain,
  recordedTakeIndex,
  recordedTakeIndexForVelocity,
} from './takeSelection'

describe('recordedTakeIndex', () => {
  it('selects the same recorded take for the same event', () => {
    expect(recordedTakeIndex('event-42', 2)).toBe(recordedTakeIndex('event-42', 2))
  })

  it('uses every available take across ordinary event ids', () => {
    const selected = new Set(
      Array.from({ length: 16 }, (_, index) => recordedTakeIndex(`hit-${index}`, 2)),
    )
    expect(selected).toEqual(new Set([0, 1]))
  })

  it('rejects an empty take collection', () => {
    expect(() => recordedTakeIndex('event', 0)).toThrow(RangeError)
  })

  it('keeps soft and hard hits in their recorded layers with a deterministic overlap', () => {
    const ranges = [[.68, 1], [0, .78]] as const
    expect(recordedTakeIndexForVelocity('soft-hit', .3, [...ranges])).toBe(1)
    expect(recordedTakeIndexForVelocity('hard-hit', .95, [...ranges])).toBe(0)
    expect(recordedTakeIndexForVelocity('edge-hit', .72, [...ranges]))
      .toBe(recordedTakeIndexForVelocity('edge-hit', .72, [...ranges]))
  })

  it('uses a monotonic curved gain while retaining exact silence and unity', () => {
    expect(drumVelocityGain(0)).toBe(0)
    expect(drumVelocityGain(.25)).toBeLessThan(drumVelocityGain(.5))
    expect(drumVelocityGain(.5)).toBeLessThan(.5)
    expect(drumVelocityGain(1)).toBe(1)
  })
})
