import { expect, it } from 'vitest'
import {
  rankAdaptivePairs,
  type AdaptivePairInput,
  type AdaptivePreferenceProfile,
} from './adaptivePairing'

function pair(
  key: string,
  audibleDistance: number,
  leftFeatures: Record<string, number>,
  rightFeatures: Record<string, number>,
): AdaptivePairInput<string> {
  return { pair: [`${key}-left`, `${key}-right`], key, audibleDistance, leftFeatures, rightFeatures }
}

it('starts with broad audible contrast and resolves ties deterministically', () => {
  const ranked = rankAdaptivePairs([
    pair('b', .8, { density: .9 }, { density: .1 }),
    pair('c', .3, { density: .7 }, { density: .3 }),
    pair('a', .8, { density: .9 }, { density: .1 }),
  ], null)

  expect(ranked.map(item => item.key)).toEqual(['a', 'b', 'c'])
  expect(ranked.every(item => item.reason === 'broad_contrast')).toBe(true)
})

it('prioritizes contrast in an unresolved feature over an already known one', () => {
  const profile: AdaptivePreferenceProfile = {
    comparisons: 8,
    learning_confidence: 1,
    feature_weights: { density: 1 },
    preferred_ranges: {
      density: { uncertainty: 0, evidence: 1 },
    },
  }
  const ranked = rankAdaptivePairs([
    pair('known-density', .5, { density: 1, timing: .5 }, { density: 0, timing: .5 }),
    pair('unknown-timing', .5, { density: .5, timing: 1 }, { density: .5, timing: 0 }),
  ], profile)

  expect(ranked[0].key).toBe('unknown-timing')
  expect(ranked[0].reason).toBe('uncertain_features')
})

it('uses a close model decision to refine a learned preference boundary', () => {
  const profile: AdaptivePreferenceProfile = {
    comparisons: 30,
    learning_confidence: 1,
    feature_weights: { density: 10 },
    preferred_ranges: {
      density: { uncertainty: 0, evidence: 1 },
    },
  }
  const ranked = rankAdaptivePairs([
    pair('far-from-boundary', .5, { density: 1 }, { density: 0 }),
    pair('near-boundary', .5, { density: .55 }, { density: .45 }),
  ], profile)

  expect(ranked[0].key).toBe('near-boundary')
  expect(ranked[0].reason).toBe('decision_boundary')
})

it('keeps a contradictory zero-evidence range in exploration', () => {
  const profile: AdaptivePreferenceProfile = {
    comparisons: 12,
    learning_confidence: .8,
    feature_weights: {},
    preferred_ranges: {
      density: { uncertainty: .2, evidence: 0 },
      timing: { uncertainty: 0, evidence: 1 },
    },
  }
  const ranked = rankAdaptivePairs([
    pair('false-range', .5, { density: 1, timing: .5 }, { density: 0, timing: .5 }),
    pair('known-range', .5, { density: .5, timing: 1 }, { density: .5, timing: 0 }),
  ], profile)

  expect(ranked[0].key).toBe('false-range')
  expect(ranked[0].reason).toBe('uncertain_features')
})
