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
})
