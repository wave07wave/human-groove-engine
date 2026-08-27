import { describe, expect, it, vi } from 'vitest'
import { claimPreview, releasePreview } from './previewCoordinator'

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
})
