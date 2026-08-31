export function recordedTakeIndex(eventId: string, takeCount: number): number {
  if (!Number.isInteger(takeCount) || takeCount < 1) {
    throw new RangeError('takeCount must be a positive integer')
  }

  let hash = 0x811c9dc5
  for (let index = 0; index < eventId.length; index += 1) {
    hash ^= eventId.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0) % takeCount
}

export type VelocityRange = readonly [minimum: number, maximum: number]

export function recordedTakeIndexForVelocity(
  eventId: string,
  velocity: number,
  ranges: VelocityRange[],
): number {
  if (ranges.length === 0) throw new RangeError('At least one velocity range is required')
  const normalized = Math.max(0, Math.min(1, velocity))
  const distances = ranges.map(([minimum, maximum]) => {
    if (minimum > maximum) throw new RangeError('Velocity range minimum cannot exceed maximum')
    if (normalized < minimum) return minimum - normalized
    if (normalized > maximum) return normalized - maximum
    return 0
  })
  const closest = Math.min(...distances)
  const eligible = distances
    .map((distance, index) => ({ distance, index }))
    .filter(candidate => candidate.distance === closest)
  return eligible[recordedTakeIndex(eventId, eligible.length)].index
}

export function drumVelocityGain(velocity: number): number {
  const normalized = Math.max(0, Math.min(1, velocity))
  if (normalized === 0) return 0
  return Math.max(.01, normalized ** 1.25)
}
