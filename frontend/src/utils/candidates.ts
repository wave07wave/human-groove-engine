import type { BassPattern } from '../types/generated'

export function replaceCandidateRevision(items: BassPattern[], next: BassPattern, previousId?: string) {
  return items.map(item => item.pattern_id === next.pattern_id || item.pattern_id === previousId ? next : item)
}
