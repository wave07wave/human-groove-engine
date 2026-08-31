import * as Tone from 'tone'
import type { Instrument } from '../types/generated'
import { drumKitProfile, type DrumSoundId } from './drumKitProfile'
import { HiHatVoice } from './hiHat'
import { RecordedDrumVoice } from './recordedDrum'

type DrumInstrument = Exclude<Instrument, 'bass'>

export class DrumKitVoice {
  private readonly master: Tone.Gain
  private readonly compressor: Tone.Compressor
  private readonly limiter: Tone.Limiter
  private readonly kick: RecordedDrumVoice
  private readonly kickFilter: Tone.Filter
  private readonly snare: RecordedDrumVoice
  private readonly snareFilter: Tone.Filter
  private readonly percussion: RecordedDrumVoice
  private readonly percussionFilter: Tone.Filter
  private readonly hiHat: HiHatVoice
  private readonly profile: ReturnType<typeof drumKitProfile>

  constructor(sound: DrumSoundId | boolean) {
    this.profile = drumKitProfile(sound)
    this.master = new Tone.Gain(Tone.dbToGain(this.profile.masterDb))
    this.compressor = new Tone.Compressor({
      threshold: this.profile.compressorThreshold,
      ratio: 2.6,
      attack: .003,
      release: .12,
      knee: 7,
    })
    this.limiter = new Tone.Limiter(-1).toDestination()
    this.master.connect(this.compressor)
    this.compressor.connect(this.limiter)

    this.kickFilter = new Tone.Filter({
      type: 'lowpass', frequency: this.profile.kickLowpassHz, rolloff: -12, Q: .25,
    }).connect(this.master)
    this.kick = new RecordedDrumVoice({
      takes: [
        { path: 'audio/kick-221145.mp3', trimDb: -4.5, velocityRange: [.68, 1] },
        { path: 'audio/kick-221144.mp3', trimDb: 0, velocityRange: [0, .78] },
      ],
      duration: this.profile.kickDuration,
      release: .025,
      volumeDb: this.profile.kickVolumeDb,
      destination: this.kickFilter,
    })

    this.snareFilter = new Tone.Filter({
      type: 'highpass', frequency: this.profile.snareHighpassHz, rolloff: -12, Q: .3,
    }).connect(this.master)
    this.snare = new RecordedDrumVoice({
      takes: [
        { path: 'audio/snare-221143.mp3', trimDb: 0 },
        { path: 'audio/snare-221142.mp3', trimDb: 0 },
      ],
      duration: this.profile.snareDecay,
      release: this.profile.warmHiHat ? .05 : .035,
      volumeDb: this.profile.snareVolumeDb,
      destination: this.snareFilter,
    })
    this.percussionFilter = new Tone.Filter({
      type: 'highpass', frequency: this.profile.percussionHighpassHz, rolloff: -12, Q: .25,
    }).connect(this.master)
    this.percussion = new RecordedDrumVoice({
      takes: [
        { path: 'audio/percussion-block-2268.mp3', trimDb: 0 },
        { path: 'audio/percussion-agogo-2260.mp3', trimDb: 0 },
      ],
      duration: this.profile.percussionDuration,
      release: this.profile.warmHiHat ? .035 : .025,
      volumeDb: this.profile.percussionVolumeDb,
      destination: this.percussionFilter,
    })
    this.hiHat = new HiHatVoice(this.profile.warmHiHat, this.master)
  }

  get input(): Tone.InputNode {
    return this.master
  }

  async ready() {
    await Promise.all([
      this.hiHat.ready(), this.kick.ready(), this.snare.ready(), this.percussion.ready(),
    ])
  }

  trigger(instrument: DrumInstrument, time: Tone.Unit.Time, velocity: number, eventId: string) {
    const gain = Math.max(.05, Math.min(1, velocity))
    if (instrument === 'closed_hat' || instrument === 'open_hat') {
      this.hiHat.trigger(instrument === 'closed_hat' ? 'closed' : 'open', time, gain, eventId)
    } else if (instrument === 'kick') {
      this.kick.trigger(time, gain, eventId)
    } else if (instrument === 'snare') {
      this.snare.trigger(time, gain, eventId)
    } else {
      this.percussion.trigger(time, gain, eventId, .78)
    }
  }

  dispose() {
    this.hiHat.dispose()
    this.kick.dispose()
    this.kickFilter.dispose()
    this.snare.dispose()
    this.snareFilter.dispose()
    this.percussion.dispose()
    this.percussionFilter.dispose()
    this.master.dispose()
    this.compressor.dispose()
    this.limiter.dispose()
  }
}
