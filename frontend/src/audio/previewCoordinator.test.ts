import { describe, expect, it, vi } from 'vitest'
import { claimPreview, isActivePreview, releasePreview, stopActivePreview } from './previewCoordinator'

describe('previewCoordinator', () => {
  it('stops the other engine before transferring transport ownership', () => {
    const stopGroove = vi.fn()
    const stopBass = vi.fn()
    claimPreview('groove', stopGroove)
    claimPreview('bass', stopBass)
    expect(stopGroove).toHaveBeenCalledOnce()
    expect(stopBass).not.toHaveBeenCalled()
    releasePreview('bass')
  })

  it('treats the full mix as a third preview owner', () => {
    const stopBass = vi.fn()
    const stopMix = vi.fn()
    claimPreview('bass', stopBass)
    claimPreview('mix', stopMix)
    expect(stopBass).toHaveBeenCalledOnce()
    expect(stopMix).not.toHaveBeenCalled()
    releasePreview('mix')
  })

  it('explicitly stops only the requested active owner', () => {
    const stopKeyboard = vi.fn(() => releasePreview('keyboard'))
    claimPreview('keyboard', stopKeyboard)

    stopActivePreview('mix')
    expect(stopKeyboard).not.toHaveBeenCalled()
    expect(isActivePreview('keyboard')).toBe(true)

    stopActivePreview('keyboard')
    expect(stopKeyboard).toHaveBeenCalledOnce()
    expect(isActivePreview('keyboard')).toBe(false)
  })
})
