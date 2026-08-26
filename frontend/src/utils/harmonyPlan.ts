export const HARMONY_ROOTS = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B']

export const HARMONY_QUALITIES = [
  ['', 'Major'], ['m', 'Minor'], ['maj7', 'Major 7'], ['7', 'Dominant 7'],
  ['m7', 'Minor 7'], ['m7b5', 'Minor 7 b5'], ['dim', 'Diminished'],
  ['dim7', 'Diminished 7'], ['aug', 'Augmented'], ['sus2', 'Sus 2'],
  ['sus4', 'Sus 4'], ['6', 'Major 6'], ['m6', 'Minor 6'], ['add9', 'Add 9'],
  ['9', 'Dominant 9'], ['11', 'Dominant 11'], ['13', 'Dominant 13'],
] as const

export type HarmonyPlanItem = { root: string, quality: string, slashBass: string, durationBars: number }

export function parseHarmonyPlan(value: string): HarmonyPlanItem[] | null {
  const symbols = value.split('|').map(item => item.trim()).filter(Boolean)
  if (!symbols.length) return null
  const parsed: HarmonyPlanItem[] = []
  for (const symbol of symbols) {
    const match = symbol.match(/^([A-G](?:#|b)?)([^/]*?)(?:\/([A-G](?:#|b)?))?$/)
    if (!match || !HARMONY_QUALITIES.some(([suffix]) => suffix === match[2])) return null
    const item = { root: match[1], quality: match[2], slashBass: match[3] ?? '', durationBars: 1 }
    const previous = parsed.at(-1)
    if (previous && previous.root === item.root && previous.quality === item.quality && previous.slashBass === item.slashBass) previous.durationBars += 1
    else parsed.push(item)
  }
  return parsed
}

export function serializeHarmonyPlan(items: HarmonyPlanItem[]): string {
  return items.flatMap(item => Array.from({ length: item.durationBars }, () => `${item.root}${item.quality}${item.slashBass ? `/${item.slashBass}` : ''}`)).join(' | ')
}
