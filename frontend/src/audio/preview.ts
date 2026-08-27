import * as Tone from 'tone'
import { prepareAudioOutput } from './audioOutput'
import type { GrooveEvent, GroovePattern, Instrument } from '../types/generated'
import { claimPreview, releasePreview } from './previewCoordinator'

let playing = false
type PreviewSynth = Tone.Synth | Tone.MembraneSynth | Tone.NoiseSynth | Tone.PolySynth
let instruments: Record<Instrument, PreviewSynth> | null = null

function disposeInstruments() {
  if (instruments) Object.values(instruments).forEach(instrument => instrument.dispose())
  instruments = null
}

function seconds(event: GrooveEvent, pattern: GroovePattern): number {
  const ticks = event.grid_tick + event.structural_offset_tick
  return ticks * 60 / (pattern.bpm * 960) + event.micro_offset_us / 1_000_000
}

export async function togglePreview(pattern: GroovePattern, onState: (value: boolean) => void) {
  const stop = () => { Tone.getTransport().stop(); Tone.getTransport().cancel(); disposeInstruments(); releasePreview('groove'); playing = false; onState(false) }
  if (playing) { stop(); return }
  claimPreview('groove', stop)
  try { await prepareAudioOutput() } catch (cause) { releasePreview('groove'); throw cause }
  disposeInstruments()
  instruments = {
    kick: new Tone.MembraneSynth({ pitchDecay: .04, octaves: 7 }).toDestination(),
    snare: new Tone.NoiseSynth({ noise: { type: 'white' }, envelope: { attack: .001, decay: .12, sustain: 0 } }).toDestination(),
    closed_hat: new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'square8' }, envelope: { attack: .001, decay: .035, sustain: 0, release: .01 }, volume: -18 }).toDestination(),
    open_hat: new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'square8' }, envelope: { attack: .001, decay: .2, sustain: .03, release: .08 }, volume: -18 }).toDestination(),
    percussion: new Tone.MembraneSynth({ pitchDecay: .015, octaves: 3 }).toDestination(),
    bass: new Tone.Synth({ oscillator: { type: 'triangle' }, envelope: { attack: .005, decay: .1, sustain: .35, release: .15 } }).toDestination(),
  }
  const transport = Tone.getTransport(); transport.cancel(); transport.seconds = 0
  for (const event of pattern.events) {
    transport.schedule(time => {
      const synth = instruments?.[event.instrument]
      const duration = Math.max(.02, event.duration_tick * 60 / (pattern.bpm * 960))
      const velocity = event.velocity / 127
      if (event.instrument === 'snare') (synth as Tone.NoiseSynth).triggerAttackRelease(duration, time, velocity)
      else if (event.instrument.includes('hat')) (synth as Tone.PolySynth).triggerAttackRelease('C7', duration, time, velocity)
      else (synth as Tone.Synth).triggerAttackRelease(event.instrument === 'bass' ? 'C2' : 'C1', duration, time, velocity)
    }, Math.max(0, seconds(event, pattern)))
  }
  const total = pattern.bars * pattern.meter.numerator * 60 * 4 / (pattern.bpm * pattern.meter.denominator)
  transport.schedule(() => { playing = false; onState(false); transport.stop(); disposeInstruments(); releasePreview('groove') }, total + .1)
  playing = true; onState(true); transport.start('+0.05')
}
