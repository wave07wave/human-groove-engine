export type PatternTiming = {
  bars: number
  bpm: number
  meter: { numerator: number, denominator: number }
}

export function patternDurationSeconds(pattern: PatternTiming) {
  return pattern.bars * pattern.meter.numerator * 60 * 4
    / (pattern.bpm * pattern.meter.denominator)
}
