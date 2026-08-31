export type AdaptivePairReason = 'broad_contrast' | 'uncertain_features' | 'decision_boundary'

export interface AdaptivePreferenceProfile {
  comparisons: number
  learning_confidence?: number
  feature_weights?: Record<string, number>
  preferred_ranges?: Record<string, {
    uncertainty: number
    evidence?: number
  }>
}

export interface AdaptivePairInput<T> {
  pair: [T, T]
  key: string
  audibleDistance: number
  leftFeatures: Record<string, number>
  rightFeatures: Record<string, number>
}

export interface AdaptivePairPlan<T> extends AdaptivePairInput<T> {
  informationScore: number
  reason: AdaptivePairReason
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function binaryEntropy(probability: number): number {
  if (probability <= 0 || probability >= 1) return 0
  return -(
    probability * Math.log(probability)
    + (1 - probability) * Math.log(1 - probability)
  ) / Math.log(2)
}

function rootMeanSquare(values: number[]): number {
  if (!values.length) return 0
  return Math.sqrt(values.reduce((total, value) => total + value ** 2, 0) / values.length)
}

export function rankAdaptivePairs<T>(
  pairs: AdaptivePairInput<T>[],
  profile: AdaptivePreferenceProfile | null,
): AdaptivePairPlan<T>[] {
  const weights = profile?.feature_weights ?? {}
  const ranges = profile?.preferred_ranges ?? {}
  const confidence = clamp(profile?.learning_confidence ?? 0)
  const maximumWeight = Math.max(0, ...Object.values(weights).map(value => Math.abs(value)))
  const coldStart = !profile?.comparisons

  return pairs.map(item => {
    const featureNames = [...new Set([
      ...Object.keys(item.leftFeatures), ...Object.keys(item.rightFeatures),
    ])].sort()
    const deltas = featureNames.map(name => (
      (item.leftFeatures[name] ?? 0) - (item.rightFeatures[name] ?? 0)
    ))
    const unresolvedDeltas = deltas.map((delta, index) => {
      const name = featureNames[index]
      const range = ranges[name]
      const rangeKnowledge = range
        ? clamp(range.evidence ?? 0) * (1 - clamp(range.uncertainty))
        : 0
      const directionalKnowledge = maximumWeight
        ? confidence * Math.abs(weights[name] ?? 0) / maximumWeight
        : 0
      return delta * (1 - Math.max(rangeKnowledge, directionalKnowledge))
    })
    const featureMagnitude = rootMeanSquare(deltas)
    const unresolvedContrast = rootMeanSquare(unresolvedDeltas)
    const logit = featureNames.reduce(
      (total, name, index) => total + (weights[name] ?? 0) * deltas[index], 0,
    )
    const probability = 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, logit))))
    const boundaryInformation = featureMagnitude * binaryEntropy(probability)
    const informationScore = coldStart
      ? clamp(item.audibleDistance)
      : 0.45 * clamp(item.audibleDistance)
        + 0.35 * clamp(unresolvedContrast)
        + 0.20 * clamp(boundaryInformation)
    const reason: AdaptivePairReason = coldStart
      ? 'broad_contrast'
      : unresolvedContrast >= boundaryInformation
        ? 'uncertain_features'
        : 'decision_boundary'
    return { ...item, informationScore, reason }
  }).sort((left, right) => (
    right.informationScore - left.informationScore || left.key.localeCompare(right.key)
  ))
}
