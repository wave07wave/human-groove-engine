import * as Tone from 'tone'
import { prepareAudioOutput } from './audioOutput'
import type { BassPattern, GroovePattern, Instrument } from '../types/generated'
import { claimPreview, releasePreview } from './previewCoordinator'

type DrumSynth = Tone.MembraneSynth | Tone.NoiseSynth | Tone.PolySynth

let playing = false
let drums: Partial<Record<Instrument, DrumSynth>> | null = null
let bass: Tone.MonoSynth | Tone.PolySynth | null = null

function tickSeconds(tick: number, bpm: number) { return tick * 60 / (bpm * 960) }

function dispose() {
  Object.values(drums ?? {}).forEach(synth => synth?.dispose())
  bass?.dispose()
  drums = null
  bass = null
}

function stop(onState: (value: boolean) => void) {
  Tone.getTransport().stop()
  Tone.getTransport().cancel()
  dispose()
  releasePreview('mix')
  playing = false
  onState(false)
}

function bassPerformance(event: BassPattern['events'][number], bpm: number) {
  const duration = Math.max(.02, tickSeconds(event.duration_tick, bpm))
  const connected = event.articulation.connection === 'staccato' ? Math.min(duration, .09) : duration
  const muted = event.articulation.technique === 'mute' ? Math.min(connected, .11) : connected
  const gain = event.velocity / 127 * (event.articulation.accent === 'accent' ? 1.08 : event.articulation.accent === 'soft' ? .72 : 1)
  return { duration: Math.max(.02, muted), gain: Math.min(1, gain) }
}

export async function toggleMixPreview(
  groove: GroovePattern,
  bassPattern: BassPattern,
  onState: (value: boolean) => void,
) {
  if (playing) { stop(onState); return }
  claimPreview('mix', () => stop(onState))
  try { await prepareAudioOutput() } catch (cause) { releasePreview('mix'); throw cause }
  dispose()
  drums = {
    kick: new Tone.MembraneSynth({ pitchDecay: .04, octaves: 7 }).toDestination(),
    snare: new Tone.NoiseSynth({ noise: { type: 'white' }, envelope: { attack: .001, decay: .12, sustain: 0 } }).toDestination(),
    closed_hat: new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'square8' }, envelope: { attack: .001, decay: .035, sustain: 0, release: .01 }, volume: -18 }).toDestination(),
    open_hat: new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'square8' }, envelope: { attack: .001, decay: .2, sustain: .03, release: .08 }, volume: -18 }).toDestination(),
    percussion: new Tone.MembraneSynth({ pitchDecay: .015, octaves: 3 }).toDestination(),
  }
  bass = bassPattern.voice_policy === 'allow_overlap'
    ? new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'triangle' }, envelope: { attack: .008, decay: .12, sustain: .48, release: .12 }, volume: -5 }).toDestination()
    : new Tone.MonoSynth({ oscillator: { type: 'triangle' }, envelope: { attack: .008, decay: .12, sustain: .48, release: .12 }, volume: -5 }).toDestination()

  const transport = Tone.getTransport()
  transport.cancel()
  transport.seconds = 0
  for (const event of groove.events) {
    if (event.instrument === 'bass') continue
    const onset = Math.max(0, tickSeconds(event.grid_tick + event.structural_offset_tick, groove.bpm) + event.micro_offset_us / 1_000_000)
    transport.schedule(time => {
      const synth = drums?.[event.instrument]
      if (!synth) return
      const duration = Math.max(.02, tickSeconds(event.duration_tick, groove.bpm))
      const gain = event.velocity / 127
      if (event.instrument === 'snare') (synth as Tone.NoiseSynth).triggerAttackRelease(duration, time, gain)
      else if (event.instrument.includes('hat')) (synth as Tone.PolySynth).triggerAttackRelease('C7', duration, time, gain)
      else (synth as Tone.MembraneSynth).triggerAttackRelease('C1', duration, time, gain)
    }, onset)
  }
  for (const event of bassPattern.events) {
    const onset = Math.max(0, tickSeconds(event.grid_tick + event.structural_offset_tick, bassPattern.bpm) + event.micro_offset_us / 1_000_000)
    const performance = bassPerformance(event, bassPattern.bpm)
    transport.schedule(time => bass?.triggerAttackRelease(Tone.Frequency(event.pitch, 'midi').toFrequency(), performance.duration, time, performance.gain), onset)
  }
  const total = Math.max(groove.bars, bassPattern.bars) * groove.meter.numerator * 60 * 4 / (groove.bpm * groove.meter.denominator)
  transport.schedule(() => stop(onState), total + .1)
  playing = true
  onState(true)
  transport.start('+0.05')
}
