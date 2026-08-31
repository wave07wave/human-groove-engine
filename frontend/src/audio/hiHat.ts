import * as Tone from 'tone'
import { hiHatProfile } from './hiHatProfile'
import { drumVelocityGain, recordedTakeIndex } from './takeSelection'

const closedSamples = [
  { path: 'audio/hihat-closed-378377.mp3', trimDb: 0 },
  { path: 'audio/hihat-closed-674296.mp3', trimDb: 0 },
]
const openSamples = [
  { path: 'audio/hihat-open-2290.mp3', trimDb: 0 },
  { path: 'audio/hihat-open-2291.mp3', trimDb: -4.5 },
]

export class HiHatVoice {
  private readonly closed: Tone.Sampler[]
  private readonly open: Tone.Sampler[]
  private readonly closedFilter: Tone.Filter
  private readonly openFilter: Tone.Filter
  private readonly profile: ReturnType<typeof hiHatProfile>
  private openUntil = 0

  constructor(warm: boolean, destination: Tone.InputNode = Tone.getDestination()) {
    this.profile = hiHatProfile(warm)
    this.closedFilter = new Tone.Filter({
      type: 'highpass', frequency: this.profile.highpassHz, rolloff: -12, Q: .35,
    }).connect(destination)
    this.openFilter = new Tone.Filter({
      type: 'highpass', frequency: this.profile.highpassHz * .78, rolloff: -12, Q: .3,
    }).connect(destination)
    this.closed = closedSamples.map(take => new Tone.Sampler({
      urls: { C4: new URL(take.path, document.baseURI).toString() },
      attack: .001, release: this.profile.release,
      volume: this.profile.closedVolume + take.trimDb,
    }).connect(this.closedFilter))
    this.open = openSamples.map(take => new Tone.Sampler({
      urls: { C4: new URL(take.path, document.baseURI).toString() },
      attack: .001, release: this.profile.release * 1.5,
      volume: this.profile.openVolume + take.trimDb,
    }).connect(this.openFilter))
  }

  async ready() {
    await Tone.loaded()
  }

  trigger(
    kind: 'closed' | 'open',
    time: Tone.Unit.Time,
    velocity: number,
    eventId: string,
    durationSeconds?: number,
  ) {
    const gain = drumVelocityGain(velocity)
    const eventTime = Tone.Time(time).toSeconds()
    if (kind === 'closed') {
      if (eventTime < this.openUntil) this.open.forEach(voice => voice.releaseAll(time))
      this.openUntil = 0
      const voice = this.closed[recordedTakeIndex(eventId, this.closed.length)]
      const duration = Math.max(.035, Math.min(this.profile.closedDuration * 1.5, durationSeconds ?? this.profile.closedDuration))
      voice.triggerAttackRelease('C4', duration, time, gain)
      return
    }
    if (eventTime < this.openUntil) this.open.forEach(voice => voice.releaseAll(time))
    const voice = this.open[recordedTakeIndex(eventId, this.open.length)]
    const duration = Math.max(.12, Math.min(this.profile.openDuration * 1.35, durationSeconds ?? this.profile.openDuration))
    voice.triggerAttackRelease('C4', duration, time, gain)
    this.openUntil = eventTime + duration
  }

  dispose() {
    this.closed.forEach(voice => voice.dispose())
    this.open.forEach(voice => voice.dispose())
    this.closedFilter.dispose()
    this.openFilter.dispose()
  }
}
