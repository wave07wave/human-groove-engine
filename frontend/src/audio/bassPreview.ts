import * as Tone from 'tone'
import { prepareAudioOutput } from './audioOutput'
import type { BassPattern } from '../types/generated'
import { claimPreview, releasePreview } from './previewCoordinator'

export type BassPreviewMode = 'bass_only' | 'bass_click' | 'bass_kick' | 'bass_chords' | 'bass_kick_chords'

let playing = false
let bassSynth: Tone.MonoSynth | Tone.PolySynth | null = null
let clickSynth: Tone.Synth | null = null
let kickSynth: Tone.MembraneSynth | null = null
let chordSynth: Tone.PolySynth | null = null

function dispose() {
  bassSynth?.dispose(); clickSynth?.dispose(); kickSynth?.dispose(); chordSynth?.dispose()
  bassSynth = null; clickSynth = null; kickSynth = null; chordSynth = null
}

function stop(onState: (value: boolean) => void) {
  Tone.getTransport().stop(); Tone.getTransport().cancel(); dispose()
  releasePreview('bass')
  playing = false; onState(false)
}

export function stopBassPreview(onState: (value: boolean) => void = () => undefined) {
  if (playing) stop(onState)
}

function tickSeconds(tick: number, bpm: number) { return tick * 60 / (bpm * 960) }

function articulationPerformance(event: BassPattern['events'][number], bpm: number) {
  const baseDuration = Math.max(.02, tickSeconds(event.duration_tick, bpm))
  const connected = event.articulation.connection === 'staccato'
    ? Math.min(baseDuration, .09)
    : event.articulation.connection === 'legato'
      ? baseDuration + tickSeconds(event.articulation.legato_overlap_tick, bpm)
      : baseDuration
  const duration = event.articulation.technique === 'ghost'
    ? Math.min(connected, .06)
    : event.articulation.technique === 'mute'
      ? Math.min(connected, .11)
      : connected
  const accent = event.articulation.accent === 'accent' ? 1.08 : event.articulation.accent === 'soft' ? .72 : 1
  const technique = event.articulation.technique === 'ghost' ? .55 : event.articulation.technique === 'mute' ? .68 : 1
  return { duration: Math.max(.02, duration), gain: Math.min(1, event.velocity / 127 * accent * technique) }
}

export async function toggleBassPreview(pattern: BassPattern, mode: BassPreviewMode, onState: (value: boolean) => void) {
  if (playing) { stop(onState); return }
  claimPreview('bass', () => stop(onState))
  try { await prepareAudioOutput() } catch (cause) { releasePreview('bass'); throw cause }
  dispose()
  bassSynth = pattern.voice_policy === 'allow_overlap'
    ? new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'triangle' }, envelope: { attack: .008, decay: .12, sustain: .48, release: .12 }, volume: -5 }).toDestination()
    : new Tone.MonoSynth({
      oscillator: { type: 'triangle' },
      envelope: { attack: .008, decay: .12, sustain: .48, release: .12 },
      filterEnvelope: { attack: .002, decay: .15, sustain: .3, release: .25, baseFrequency: 75, octaves: 2.4 },
      volume: -5,
    }).toDestination()
  const transport = Tone.getTransport(); transport.cancel(); transport.seconds = 0
  for (const event of pattern.events) {
    const onset = Math.max(0, tickSeconds(event.grid_tick + event.structural_offset_tick, pattern.bpm) + event.micro_offset_us / 1_000_000)
    const performance = articulationPerformance(event, pattern.bpm)
    transport.schedule(time => bassSynth?.triggerAttackRelease(Tone.Frequency(event.pitch, 'midi').toFrequency(), performance.duration, time, performance.gain), onset)
  }

  if (mode === 'bass_click') {
    clickSynth = new Tone.Synth({ oscillator: { type: 'sine' }, envelope: { attack: .001, decay: .025, sustain: 0, release: .01 }, volume: -15 }).toDestination()
    const beatTick = 960 * 4 / pattern.meter.denominator
    const totalTick = pattern.bars * pattern.meter.numerator * beatTick
    for (let tick = 0; tick < totalTick; tick += beatTick) {
      const accent = tick % (pattern.meter.numerator * beatTick) === 0
      transport.schedule(time => clickSynth?.triggerAttackRelease(accent ? 'C6' : 'G5', .025, time, accent ? .72 : .38), tickSeconds(tick, pattern.bpm))
    }
  }

  if (mode === 'bass_kick' || mode === 'bass_kick_chords') {
    kickSynth = new Tone.MembraneSynth({ pitchDecay: .04, octaves: 6, volume: -7 }).toDestination()
    for (const kick of pattern.groove_context?.kick_events ?? []) {
      const onset = Math.max(0, tickSeconds(kick.grid_tick + kick.structural_offset_tick, pattern.bpm) + kick.micro_offset_us / 1_000_000)
      transport.schedule(time => kickSynth?.triggerAttackRelease('C1', .13, time, kick.velocity / 127), onset)
    }
  }

  if (mode === 'bass_chords' || mode === 'bass_kick_chords') {
    chordSynth = new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'sine' }, envelope: { attack: .03, decay: .18, sustain: .18, release: .35 }, volume: -17 }).toDestination()
    for (const harmony of pattern.harmony.events) {
      if (!harmony.chord) continue
      const notes = harmony.chord.spelled_tones.slice(0, 4).map(tone => {
        const midi = 60 + tone.pitch_class + (tone.pitch_class > 7 ? -12 : 0)
        return Tone.Frequency(midi, 'midi').toFrequency()
      })
      transport.schedule(time => chordSynth?.triggerAttackRelease(notes, Math.max(.1, tickSeconds(harmony.duration_tick, pattern.bpm) - .06), time, .34), tickSeconds(harmony.start_tick, pattern.bpm))
    }
  }

  const total = pattern.bars * pattern.meter.numerator * 60 * 4 / (pattern.bpm * pattern.meter.denominator)
  transport.schedule(() => stop(onState), total + .1)
  playing = true; onState(true); transport.start('+0.05')
}
