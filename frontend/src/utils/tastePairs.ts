import type { GroovePattern, GroovePreferenceSummary } from '../types/generated'
import { rankAdaptivePairs, type AdaptivePairPlan } from './adaptivePairing'

export type PreferencePair = [GroovePattern, GroovePattern]

function preferenceVector(pattern: GroovePattern): Record<string, number> {
  const dna = pattern.analysis?.measured_dna
  if (!dna) return {}
  return Object.fromEntries(
    Object.entries(dna).map(([name, value]) => [name, Number(value)]),
  )
}

function pairDistance(left: GroovePattern, right: GroovePattern): number {
  const leftEvents = new Set(
    left.events.map(event => `${event.instrument}:${event.grid_tick}:${event.primary_role}`),
  )
  const rightEvents = new Set(
    right.events.map(event => `${event.instrument}:${event.grid_tick}:${event.primary_role}`),
  )
  const union = new Set([...leftEvents, ...rightEvents])
  const intersection = [...leftEvents].filter(value => rightEvents.has(value)).length
  const eventDistance = 1 - intersection / Math.max(1, union.size)
  const leftDNA = left.analysis?.measured_dna
  const rightDNA = right.analysis?.measured_dna
  const dnaDistance = leftDNA && rightDNA
    ? Object.keys(leftDNA).reduce(
      (total, key) => total + Math.abs(
        Number(leftDNA[key as keyof typeof leftDNA]) - Number(rightDNA[key as keyof typeof rightDNA]),
      ),
      0,
    ) / Math.max(1, Object.keys(leftDNA).length)
    : 0
  return 0.72 * eventDistance + 0.28 * dnaDistance
}

export function buildPreferencePairPlans(
  candidates: GroovePattern[],
  preference: GroovePreferenceSummary | null = null,
): AdaptivePairPlan<GroovePattern>[] {
  const unique = [...new Map(candidates.map(candidate => [candidate.pattern_id, candidate])).values()]
  const pairs = []
  for (let left = 0; left < unique.length; left += 1) {
    for (let right = left + 1; right < unique.length; right += 1) {
      const pair: PreferencePair = [unique[left], unique[right]]
      pairs.push({
        pair,
        audibleDistance: pairDistance(...pair),
        key: [pair[0].pattern_id, pair[1].pattern_id].sort().join('|'),
        leftFeatures: preferenceVector(pair[0]),
        rightFeatures: preferenceVector(pair[1]),
      })
    }
  }
  return rankAdaptivePairs(pairs, preference)
}

export function buildPreferencePairs(
  candidates: GroovePattern[], preference: GroovePreferenceSummary | null = null,
): PreferencePair[] {
  return buildPreferencePairPlans(candidates, preference).map(item => item.pair)
}
