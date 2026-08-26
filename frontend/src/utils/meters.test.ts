import { describe, expect, it } from 'vitest'
import { METERS, METER_OPTIONS } from './meters'

describe('meter options', () => {
  it('provides distinct 5/4 and 5/8 definitions', () => {
    expect(METER_OPTIONS).toContain('5/4')
    expect(METER_OPTIONS).toContain('5/8')
    expect(METERS['5/4'].grouping).toEqual([3, 2])
    expect(METERS['5/8'].grouping).toEqual([3, 2])
    expect(METERS['5/4'].denominator).toBe(4)
    expect(METERS['5/8'].denominator).toBe(8)
  })
})
