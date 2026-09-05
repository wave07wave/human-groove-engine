import { describe, expect, it } from 'vitest'
import type { KeyboardEvent } from '../types/generated'
import { layoutKeyboardBarEvents } from './keyboardLayout'

function keyboardEvent(eventId: string, gridTick: number): KeyboardEvent {
  return {
    event_id: eventId,
    grid_tick: gridTick,
    micro_offset_us: 0,
    duration_tick: 120,
    pitches: [60],
    velocities: [90],
    instrument: 'acoustic_piano',
    role: 'comp',
    hand: 'right',
    articulation: 'normal',
    locked: false,
    origin: 'generated',
  }
}

describe('layoutKeyboardBarEvents', () => {
  it('moves nearby events onto separate lanes and reuses a lane after the minimum gap', () => {
    const events = [
      keyboardEvent('late', 720),
      keyboardEvent('first', 0),
      keyboardEvent('nearby', 120),
    ]

    const result = layoutKeyboardBarEvents(events, 3840)

    expect(result.map(item => [item.event.event_id, item.lane])).toEqual([
      ['first', 0],
      ['nearby', 1],
      ['late', 0],
    ])
    expect(events.map(event => event.event_id)).toEqual(['late', 'first', 'nearby'])
  })

  it('lays out events independently within their local bar position', () => {
    const result = layoutKeyboardBarEvents([
      keyboardEvent('bar-two-start', 3840),
      keyboardEvent('bar-two-nearby', 3960),
    ], 3840)

    expect(result.map(item => item.lane)).toEqual([0, 1])
  })

  it('reserves the left-shifted visual interval of right-edge events', () => {
    const result = layoutKeyboardBarEvents([
      keyboardEvent('three-quarters', 2880),
      keyboardEvent('right-edge', 3360),
    ], 3840)

    expect(result.find(item => item.event.event_id === 'three-quarters')?.lane)
      .not.toBe(result.find(item => item.event.event_id === 'right-edge')?.lane)
  })
})
