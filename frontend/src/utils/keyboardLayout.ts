import type { KeyboardEvent } from '../types/generated'

export function layoutKeyboardBarEvents(events: KeyboardEvent[], barTicks: number) {
  const laneEnds: number[] = []
  // At the minimum timeline width, the widest event occupies about 17% of a bar.
  // Events near the right edge are anchored by their right side in CSS, so their
  // visual interval begins before their musical position.
  const occupiedFraction = 0.17
  return [...events]
    .map(event => {
      const position = (event.grid_tick % barTicks) / barTicks
      const edge = position > 0.86
      return {
        event,
        edge,
        visualStart: edge ? Math.max(0, position - occupiedFraction) : position,
        visualEnd: edge ? position : Math.min(1, position + occupiedFraction),
      }
    })
    .sort((left, right) => left.visualStart - right.visualStart
      || left.event.grid_tick - right.event.grid_tick)
    .map(({ event, visualStart, visualEnd, edge }) => {
      let lane = laneEnds.findIndex(end => visualStart >= end)
      if (lane < 0) lane = laneEnds.length
      laneEnds[lane] = visualEnd
      return { event, lane, edge }
    })
}
