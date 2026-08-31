import { expect, it } from 'vitest'
import { DRUM_SOUND_OPTIONS, drumKitProfile } from './drumKitProfile'

it('keeps both drum profiles below unity and gives Warm Pocket longer decays', () => {
  const tight = drumKitProfile(false)
  const warm = drumKitProfile(true)
  expect(tight.masterDb).toBeLessThan(0)
  expect(warm.masterDb).toBeLessThan(0)
  expect(warm.kickDuration).toBeGreaterThan(tight.kickDuration)
  expect(warm.snareDecay).toBeGreaterThan(tight.snareDecay)
  expect(warm.kickLowpassHz).toBeLessThan(tight.kickLowpassHz)
  expect(warm.percussionDuration).toBeGreaterThan(tight.percussionDuration)
  expect(warm.percussionHighpassHz).toBeLessThan(tight.percussionHighpassHz)
})

it('offers four distinct, safely gain-staged drum sound choices', () => {
  expect(DRUM_SOUND_OPTIONS).toHaveLength(4)
  const tight = drumKitProfile('studio-tight-v1')
  const profiles = DRUM_SOUND_OPTIONS.map(option => drumKitProfile(option.id))
  expect(profiles.every(profile => profile.masterDb < 0)).toBe(true)
  expect(drumKitProfile('club-punch-v1').kickLowpassHz).toBeLessThan(tight.kickLowpassHz)
  expect(drumKitProfile('vintage-dust-v1').snareDecay).toBeGreaterThan(tight.snareDecay)
})
