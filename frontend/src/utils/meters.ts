import type { MeterDefinition } from '../types/generated'

export const METERS: Record<string, MeterDefinition> = {
  '4/4': { numerator: 4, denominator: 4, grouping: [2, 2], subdivisions_per_quarter: 4 },
  '3/4': { numerator: 3, denominator: 4, grouping: [2, 2, 2], subdivisions_per_quarter: 4 },
  '5/4': { numerator: 5, denominator: 4, grouping: [3, 2], subdivisions_per_quarter: 4 },
  '5/8': { numerator: 5, denominator: 8, grouping: [3, 2], subdivisions_per_quarter: 4 },
  '6/8': { numerator: 6, denominator: 8, grouping: [3, 3], subdivisions_per_quarter: 4 },
  '12/8': { numerator: 12, denominator: 8, grouping: [3, 3, 3, 3], subdivisions_per_quarter: 4 },
}

export const METER_OPTIONS = Object.keys(METERS)
