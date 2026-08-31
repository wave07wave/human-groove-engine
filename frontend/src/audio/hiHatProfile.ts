export type HiHatProfile = {
  highpassHz: number
  closedDuration: number
  openDuration: number
  release: number
  closedVolume: number
  openVolume: number
}

export function hiHatProfile(warm: boolean): HiHatProfile {
  return warm ? {
    highpassHz: 1800, closedDuration: .17, openDuration: 1.15, release: .035,
    closedVolume: -7, openVolume: -10,
  } : {
    highpassHz: 2600, closedDuration: .11, openDuration: .72, release: .022,
    closedVolume: -9, openVolume: -12,
  }
}
