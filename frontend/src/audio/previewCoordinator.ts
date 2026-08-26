type PreviewOwner = 'groove' | 'bass'

let active: { owner: PreviewOwner, stop: () => void } | null = null

export function claimPreview(owner: PreviewOwner, stop: () => void) {
  if (active && active.owner !== owner) active.stop()
  active = { owner, stop }
}

export function releasePreview(owner: PreviewOwner) {
  if (active?.owner === owner) active = null
}
