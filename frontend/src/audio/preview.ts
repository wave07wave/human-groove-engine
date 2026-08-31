import * as Tone from 'tone'
import { prepareAudioOutput } from './audioOutput'
import type { GrooveEvent, GroovePattern } from '../types/generated'
import { claimPreview, releasePreview } from './previewCoordinator'
import { DrumKitVoice } from './drumKit'
import { drumKitProfile, type DrumSoundId } from './drumKitProfile'

let playing = false
let playingPatternId: string | null = null
let drumKit: DrumKitVoice | null = null
let bass: Tone.Synth | null = null

function disposeInstruments() {
  drumKit?.dispose()
  bass?.dispose()
  drumKit = null
  bass = null
}

function stop(onState: (value: boolean) => void) {
  Tone.getTransport().stop(); Tone.getTransport().cancel(); disposeInstruments()
  releasePreview('groove')
  playing = false; playingPatternId = null; onState(false)
}

export function stopGroovePreview(onState: (value: boolean) => void = () => undefined) {
  if (playing) stop(onState)
}

function seconds(event: GrooveEvent, pattern: GroovePattern): number {
  const ticks = event.grid_tick + event.structural_offset_tick
  return ticks * 60 / (pattern.bpm * 960) + event.micro_offset_us / 1_000_000
}

export async function togglePreview(pattern: GroovePattern, onState: (value: boolean) => void) {
  if (playing) {
    const shouldSwitch = playingPatternId !== pattern.pattern_id
    stop(onState)
    if (!shouldSwitch) return
  }
  claimPreview('groove', () => stop(onState))
  try { await prepareAudioOutput() } catch (cause) { releasePreview('groove'); throw cause }
  disposeInstruments()
  const sound = pattern.metadata.render_profile as DrumSoundId
  const soundProfile = drumKitProfile(sound)
  const nextKit = new DrumKitVoice(sound)
  drumKit = nextKit
  try { await nextKit.ready() } catch (cause) { disposeInstruments(); releasePreview('groove'); throw cause }
  bass = new Tone.Synth({ oscillator: { type: soundProfile.warmBass ? 'sine' : 'triangle' }, envelope: { attack: soundProfile.warmBass ? .011 : .005, decay: soundProfile.warmBass ? .18 : .1, sustain: soundProfile.warmBass ? .42 : .35, release: soundProfile.warmBass ? .24 : .15 }, volume: -5 }).connect(nextKit.input)
  const transport = Tone.getTransport(); transport.cancel(); transport.seconds = 0
  for (const event of pattern.events) {
    transport.schedule(time => {
      const duration = Math.max(.02, event.duration_tick * 60 / (pattern.bpm * 960))
      const velocity = event.velocity / 127
      if (event.instrument !== 'bass') {
        drumKit?.trigger(event.instrument, time, velocity, event.event_id)
        return
      }
      bass?.triggerAttackRelease('C2', duration, time, velocity)
    }, Math.max(0, seconds(event, pattern)))
  }
  const total = pattern.bars * pattern.meter.numerator * 60 * 4 / (pattern.bpm * pattern.meter.denominator)
  transport.schedule(() => { playing = false; playingPatternId = null; onState(false); transport.stop(); disposeInstruments(); releasePreview('groove') }, total + .1)
  playing = true; playingPatternId = pattern.pattern_id; onState(true); transport.start('+0.05')
}
