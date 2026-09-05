import * as Tone from 'tone'
import type { KeyboardInstrument, KeyboardPattern } from '../types/generated'
import { prepareAudioOutput } from './audioOutput'
import { claimPreview, isActivePreview, releasePreview } from './previewCoordinator'

export type KeyboardVoices = Record<KeyboardInstrument, Tone.PolySynth>

let playing = false
let voices: KeyboardVoices | null = null
let startToken = 0

function tickSeconds(tick: number, bpm: number) { return tick * 60 / (bpm * 960) }

export function createKeyboardVoices(destination?: Tone.InputNode): KeyboardVoices {
  const connect = (synth: Tone.PolySynth) => destination ? synth.connect(destination) : synth.toDestination()
  return {
    acoustic_piano: connect(new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: 'triangle8' }, envelope: { attack: .004, decay: .32, sustain: .15, release: .45 }, volume: -13,
    })),
    tonewheel_organ: connect(new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: 'sine4' }, envelope: { attack: .018, decay: .08, sustain: .78, release: .24 }, volume: -15,
    })),
    electric_piano: connect(new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: 'sine8' }, envelope: { attack: .008, decay: .42, sustain: .24, release: .62 }, volume: -13,
    })),
    celeste: connect(new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: 'sine' }, envelope: { attack: .002, decay: .22, sustain: .05, release: .35 }, volume: -17,
    })),
  }
}

export function disposeKeyboardVoices(collection: KeyboardVoices | null) {
  if (!collection) return
  Object.values(collection).forEach(voice => voice.dispose())
}

export function scheduleKeyboardPattern(
  pattern: KeyboardPattern,
  collection: KeyboardVoices,
  transport = Tone.getTransport(),
) {
  for (const event of pattern.events) {
    const onset = Math.max(0, tickSeconds(event.grid_tick, pattern.bpm) + event.micro_offset_us / 1_000_000)
    const baseDuration = Math.max(.025, tickSeconds(event.duration_tick, pattern.bpm))
    const duration = event.articulation === 'staccato' ? Math.min(.13, baseDuration) : baseDuration
    const notes = event.pitches.map(pitch => Tone.Frequency(pitch, 'midi').toFrequency())
    transport.schedule(time => notes.forEach((note, index) => {
      const gain = Math.min(1, event.velocities[index] / 127)
      collection[event.instrument].triggerAttackRelease(note, duration, time, gain)
    }), onset)
  }
}

function stop(onState: (value: boolean) => void) {
  startToken += 1
  Tone.getTransport().stop()
  Tone.getTransport().cancel()
  disposeKeyboardVoices(voices)
  voices = null
  releasePreview('keyboard')
  playing = false
  onState(false)
}

export function stopKeyboardPreview(onState: (value: boolean) => void) {
  if (playing || isActivePreview('keyboard')) stop(onState)
  else onState(false)
}

export async function toggleKeyboardPreview(
  pattern: KeyboardPattern,
  onState: (value: boolean) => void,
) {
  if (playing) { stop(onState); return }
  const token = ++startToken
  claimPreview('keyboard', () => stop(onState))
  try { await prepareAudioOutput() } catch (cause) {
    if (token !== startToken) return
    releasePreview('keyboard')
    throw cause
  }
  if (token !== startToken) return
  disposeKeyboardVoices(voices)
  voices = createKeyboardVoices()
  const transport = Tone.getTransport()
  transport.cancel()
  transport.seconds = 0
  scheduleKeyboardPattern(pattern, voices, transport)
  const total = pattern.bars * pattern.meter.numerator * 60 * 4
    / (pattern.bpm * pattern.meter.denominator)
  transport.schedule(() => stop(onState), total + .1)
  playing = true
  onState(true)
  transport.start('+0.05')
}
