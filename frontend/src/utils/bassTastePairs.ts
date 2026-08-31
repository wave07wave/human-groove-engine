import type { BassPattern, BassPreferenceSummary } from '../types/generated'
import { rankAdaptivePairs, type AdaptivePairPlan } from './adaptivePairing'

export type BassPreferencePair = [BassPattern, BassPattern]

function preferenceVector(pattern: BassPattern): Record<string, number> {
  const atomic = pattern.analysis?.atomic
  const dna = pattern.analysis?.dna
  if (!atomic || !dna) return {}
  return {
    syncopation: atomic.syncopation_index,
    density: Math.min(1, atomic.onset_density * 1.7),
    silence: atomic.silence_ratio,
    root_usage: atomic.root_ratio,
    chromatic_tolerance: Math.min(1, atomic.chromatic_ratio * 4),
    pitch_motion: dna.melodic_motion,
    register: Math.max(0, Math.min(1, (atomic.register_mean - 28) / 32)),
    kick_relation: dna.kick_relationship_quality ?? .5,
    timing: dna.timing_character_strength,
    duration: Math.min(1, Math.sqrt(Math.max(0, atomic.duration_variance)) / 960),
  }
}

function pairDistance(left: BassPattern, right: BassPattern): number {
  const leftEvents = new Set(left.events.map(event => [
    event.grid_tick, event.pitch, event.rhythmic_role, event.articulation.connection,
  ].join(':')))
  const rightEvents = new Set(right.events.map(event => [
    event.grid_tick, event.pitch, event.rhythmic_role, event.articulation.connection,
  ].join(':')))
  const union = new Set([...leftEvents, ...rightEvents])
  const intersection = [...leftEvents].filter(value => rightEvents.has(value)).length
  const eventDistance = 1 - intersection / Math.max(1, union.size)
  const leftVector = Object.values(preferenceVector(left))
  const rightVector = Object.values(preferenceVector(right))
  const featureDistance = leftVector.length && leftVector.length === rightVector.length
    ? leftVector.reduce((total, value, index) => (
      total + Math.abs(value - rightVector[index])
    ), 0) / leftVector.length
    : 0
  return .68 * eventDistance + .32 * featureDistance
}

export function buildBassPreferencePairPlans(
  candidates: BassPattern[],
  preference: BassPreferenceSummary | null = null,
): AdaptivePairPlan<BassPattern>[] {
  const unique = [...new Map(candidates.map(candidate => [candidate.pattern_id, candidate])).values()]
  const pairs = []
  for (let left = 0; left < unique.length; left += 1) {
    for (let right = left + 1; right < unique.length; right += 1) {
      const pair: BassPreferencePair = [unique[left], unique[right]]
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

export function buildBassPreferencePairs(
  candidates: BassPattern[], preference: BassPreferenceSummary | null = null,
): BassPreferencePair[] {
  return buildBassPreferencePairPlans(candidates, preference).map(item => item.pair)
}
