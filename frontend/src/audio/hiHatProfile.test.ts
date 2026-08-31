import { expect, it } from 'vitest'
import { hiHatProfile } from './hiHatProfile'

it('keeps open hats longer and makes the warm profile darker', () => {
  const tight = hiHatProfile(false)
  const warm = hiHatProfile(true)
  expect(tight.openDuration).toBeGreaterThan(tight.closedDuration * 4)
  expect(warm.openDuration).toBeGreaterThan(warm.closedDuration * 4)
  expect(warm.highpassHz).toBeLessThan(tight.highpassHz)
  expect(warm.openDuration).toBeGreaterThan(tight.openDuration)
})
