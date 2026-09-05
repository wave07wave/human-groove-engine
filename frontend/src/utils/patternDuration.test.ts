import { describe, expect, it } from 'vitest'
import { patternDurationSeconds } from './patternDuration'

describe('patternDurationSeconds', () => {
  it('uses each pattern own tempo and meter', () => {
    expect(patternDurationSeconds({
      bars: 4,
      bpm: 120,
      meter: { numerator: 4, denominator: 4 },
    })).toBe(8)
    expect(patternDurationSeconds({
      bars: 4,
      bpm: 60,
      meter: { numerator: 3, denominator: 4 },
    })).toBe(12)
    expect(patternDurationSeconds({
      bars: 2,
      bpm: 120,
      meter: { numerator: 6, denominator: 8 },
    })).toBe(3)
  })
})
