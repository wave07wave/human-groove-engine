export type DrumKitProfile = {
  kickDuration: number
  kickLowpassHz: number
  kickVolumeDb: number
  snareDecay: number
  snareHighpassHz: number
  snareVolumeDb: number
  percussionDuration: number
  percussionHighpassHz: number
  percussionVolumeDb: number
  masterDb: number
  compressorThreshold: number
  warmHiHat: boolean
  warmBass: boolean
}

export type DrumSoundId = 'studio-tight-v1' | 'warm-pocket-v1' | 'club-punch-v1' | 'vintage-dust-v1'

export const DRUM_SOUND_OPTIONS: { id: DrumSoundId, label: string }[] = [
  { id: 'studio-tight-v1', label: 'Studio Tight · タイトで明瞭' },
  { id: 'warm-pocket-v1', label: 'Warm Pocket · 柔らかく太い' },
  { id: 'club-punch-v1', label: 'Club Punch · 深く力強い' },
  { id: 'vintage-dust-v1', label: 'Vintage Dust · 乾いた質感' },
]

export function drumKitProfile(sound: DrumSoundId | boolean): DrumKitProfile {
  const profile = typeof sound === 'boolean' ? (sound ? 'warm-pocket-v1' : 'studio-tight-v1') : sound
  if (profile === 'warm-pocket-v1') return { kickDuration:.15,kickLowpassHz:4600,kickVolumeDb:-2,snareDecay:.46,snareHighpassHz:80,snareVolumeDb:-5,percussionDuration:.17,percussionHighpassHz:180,percussionVolumeDb:-9,masterDb:-5,compressorThreshold:-15,warmHiHat:true,warmBass:true }
  if (profile === 'club-punch-v1') return { kickDuration:.18,kickLowpassHz:3800,kickVolumeDb:-1,snareDecay:.28,snareHighpassHz:145,snareVolumeDb:-4,percussionDuration:.11,percussionHighpassHz:350,percussionVolumeDb:-10,masterDb:-5,compressorThreshold:-18,warmHiHat:false,warmBass:true }
  if (profile === 'vintage-dust-v1') return { kickDuration:.18,kickLowpassHz:3300,kickVolumeDb:-4,snareDecay:.54,snareHighpassHz:65,snareVolumeDb:-7,percussionDuration:.21,percussionHighpassHz:150,percussionVolumeDb:-11,masterDb:-7,compressorThreshold:-12,warmHiHat:true,warmBass:false }
  return { kickDuration:.12,kickLowpassHz:7200,kickVolumeDb:-3,snareDecay:.34,snareHighpassHz:110,snareVolumeDb:-6,percussionDuration:.13,percussionHighpassHz:260,percussionVolumeDb:-10,masterDb:-6,compressorThreshold:-13,warmHiHat:false,warmBass:false }
}
