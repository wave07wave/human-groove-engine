import { describe, expect, it } from 'vitest'
import type { DetroitKeyboardSettings } from '../types/generated'
import { normalizedKeyboardBlend, withKeyboardBlendInfluence } from './detroitKeyboard'

describe('keyboard blend helpers', () => {
  it('prevents the final non-zero influence from being set to zero', () => {
    const settings: DetroitKeyboardSettings = {
      mode: 'blend',
      blend: { earl: 0, joe: 0, johnny: .2 },
    }

    const result = withKeyboardBlendInfluence(settings, 'johnny', 0)

    expect(result.blend).toEqual({ earl: 0, joe: 0, johnny: .01 })
    expect(settings.blend).toEqual({ earl: 0, joe: 0, johnny: .2 })
  })

  it('normalizes displayed percentages without changing stored relative weights', () => {
    expect(normalizedKeyboardBlend({ earl: .2, joe: .3, johnny: .5 })).toEqual({
      earl: .2,
      joe: .3,
      johnny: .5,
    })
    expect(normalizedKeyboardBlend({ earl: 1, joe: 1, johnny: 2 })).toEqual({
      earl: .25,
      joe: .25,
      johnny: .5,
    })
  })
})
