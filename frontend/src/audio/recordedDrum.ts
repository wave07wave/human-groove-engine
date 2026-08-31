import * as Tone from 'tone'
import {
  drumVelocityGain,
  recordedTakeIndexForVelocity,
  type VelocityRange,
} from './takeSelection'

export type RecordedDrumTake = {
  path: string
  trimDb: number
  velocityRange?: VelocityRange
}

type RecordedDrumOptions = {
  takes: RecordedDrumTake[]
  duration: number
  release: number
  volumeDb: number
  destination: Tone.InputNode
}

export class RecordedDrumVoice {
  private readonly voices: Tone.Sampler[]
  private readonly velocityRanges: VelocityRange[]
  private readonly duration: number

  constructor(options: RecordedDrumOptions) {
    if (options.takes.length === 0) throw new RangeError('Recorded drum requires at least one take')
    this.duration = options.duration
    this.velocityRanges = options.takes.map(take => take.velocityRange ?? [0, 1])
    this.voices = options.takes.map(take => new Tone.Sampler({
      urls: { C4: new URL(take.path, document.baseURI).toString() },
      attack: .001,
      release: options.release,
      volume: options.volumeDb + take.trimDb,
    }).connect(options.destination))
  }

  async ready() {
    await Tone.loaded()
  }

  trigger(time: Tone.Unit.Time, velocity: number, eventId: string, gainScale = 1) {
    const take = recordedTakeIndexForVelocity(eventId, velocity, this.velocityRanges)
    const gain = Math.max(0, Math.min(1, drumVelocityGain(velocity) * gainScale))
    this.voices[take].triggerAttackRelease('C4', this.duration, time, gain)
  }

  dispose() {
    this.voices.forEach(voice => voice.dispose())
  }
}
