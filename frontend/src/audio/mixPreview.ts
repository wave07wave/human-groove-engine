import * as Tone from 'tone'
import { prepareAudioOutput } from './audioOutput'
import type { BassPattern, GroovePattern } from '../types/generated'
import { claimPreview, releasePreview } from './previewCoordinator'
import { DrumKitVoice } from './drumKit'
import { drumKitProfile, type DrumSoundId } from './drumKitProfile'

let playing = false
let drumKit: DrumKitVoice | null = null
let bass: Tone.MonoSynth | Tone.PolySynth | null = null

function tickSeconds(tick: number, bpm: number) { return tick * 60 / (bpm * 960) }

function dispose() {
  drumKit?.dispose()
  bass?.dispose()
  drumKit = null
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
  const soundProfile = drumKitProfile(groove.metadata.render_profile as DrumSoundId)
  const nextKit = new DrumKitVoice(groove.metadata.render_profile as DrumSoundId)
  drumKit = nextKit
  try { await nextKit.ready() } catch (cause) { dispose(); releasePreview('mix'); throw cause }
  bass = bassPattern.voice_policy === 'allow_overlap'
    ? new Tone.PolySynth(Tone.Synth, { oscillator: { type: soundProfile.warmBass ? 'sine' : 'triangle' }, envelope: { attack: soundProfile.warmBass ? .012 : .008, decay: soundProfile.warmBass ? .2 : .12, sustain: soundProfile.warmBass ? .54 : .48, release: soundProfile.warmBass ? .22 : .12 }, volume: -5 }).connect(nextKit.input)
    : new Tone.MonoSynth({ oscillator: { type: soundProfile.warmBass ? 'sine' : 'triangle' }, envelope: { attack: soundProfile.warmBass ? .012 : .008, decay: soundProfile.warmBass ? .2 : .12, sustain: soundProfile.warmBass ? .54 : .48, release: soundProfile.warmBass ? .22 : .12 }, volume: -5 }).connect(nextKit.input)

  const transport = Tone.getTransport()
  transport.cancel()
  transport.seconds = 0
  for (const event of groove.events) {
    if (event.instrument === 'bass') continue
    const instrument = event.instrument
    const onset = Math.max(0, tickSeconds(event.grid_tick + event.structural_offset_tick, groove.bpm) + event.micro_offset_us / 1_000_000)
    transport.schedule(time => {
      drumKit?.trigger(instrument, time, event.velocity / 127, event.event_id)
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
