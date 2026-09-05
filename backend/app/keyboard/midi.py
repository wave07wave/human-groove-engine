from __future__ import annotations

from io import BytesIO

import mido

from app.config import PPQ

from .models import KeyboardPattern

PROGRAMS = {
    "acoustic_piano": 0,
    "electric_piano": 4,
    "celeste": 8,
    "tonewheel_organ": 16,
}


def _bpm_at(pattern: KeyboardPattern, tick: int) -> float:
    active = pattern.tempo_map.segments[0]
    for segment in pattern.tempo_map.segments[1:]:
        if segment.start_tick > tick:
            break
        active = segment
    return active.bpm


def _delta_messages(events):
    events.sort(key=lambda item: (item[0], item[1]))
    previous = 0
    result = []
    for absolute, _, message in events:
        message.time = max(0, int(absolute - previous))
        previous = absolute
        result.append(message)
    return result


def _rendered_notes(pattern: KeyboardPattern, instrument: str):
    final_tick = pattern.bars * pattern.meter.bar_ticks
    by_onset_pitch: dict[tuple[int, int], list[int]] = {}
    for event in pattern.events:
        if event.instrument != instrument:
            continue
        tempo = mido.bpm2tempo(_bpm_at(pattern, event.grid_tick))
        micro_tick = round(
            mido.second2tick(event.micro_offset_us / 1_000_000, PPQ, tempo)
        )
        onset = min(final_tick - 1, max(0, event.grid_tick + micro_tick))
        natural_stop = min(final_tick, max(onset + 1, onset + event.duration_tick))
        for pitch, velocity in zip(event.pitches, event.velocities, strict=True):
            key = (onset, pitch)
            if key in by_onset_pitch:
                by_onset_pitch[key][0] = max(by_onset_pitch[key][0], natural_stop)
                by_onset_pitch[key][1] = max(by_onset_pitch[key][1], velocity)
            else:
                by_onset_pitch[key] = [natural_stop, velocity]

    rendered = [
        [onset, stop_velocity[0], pitch, stop_velocity[1]]
        for (onset, pitch), stop_velocity in by_onset_pitch.items()
    ]
    rendered.sort(key=lambda item: (item[2], item[0]))
    by_pitch: dict[int, list[list[int]]] = {}
    for note in rendered:
        by_pitch.setdefault(note[2], []).append(note)
    for notes in by_pitch.values():
        for current, following in zip(notes, notes[1:]):
            current[1] = max(current[0] + 1, min(current[1], following[0]))
    return sorted(rendered, key=lambda item: (item[0], item[2]))


def export_keyboard_midi(pattern: KeyboardPattern) -> bytes:
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    settings = pattern.metadata.detroit_keyboard
    metadata_events = [
        (0, 0, mido.MetaMessage("track_name", name="Human Keys Engine")),
        (
            0,
            0,
            mido.MetaMessage(
                "time_signature",
                numerator=pattern.meter.numerator,
                denominator=pattern.meter.denominator,
            ),
        ),
        (
            0,
            0,
            mido.MetaMessage(
                "text",
                text=(
                    f"engine={pattern.metadata.engine_version};"
                    f"schema={pattern.metadata.schema_version};"
                    f"seed={pattern.metadata.master_seed};"
                    f"rng={pattern.metadata.rng_algorithm};"
                    f"keyboard_generation={pattern.metadata.keyboard_generation_version};"
                    f"keyboard_analysis={pattern.metadata.keyboard_analysis_version};"
                    f"detroit_keyboard={settings.mode};"
                    f"blend={settings.blend.earl:.4f},{settings.blend.joe:.4f},"
                    f"{settings.blend.johnny:.4f}"
                ),
            ),
        ),
    ]
    final_tick = pattern.bars * pattern.meter.bar_ticks
    metadata_events.extend(
        (
            segment.start_tick,
            0,
            mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(segment.bpm)),
        )
        for segment in pattern.tempo_map.segments
        if segment.start_tick < final_tick
    )
    metadata_events.append((final_tick, 3, mido.MetaMessage("end_of_track")))
    midi.tracks.append(mido.MidiTrack(_delta_messages(metadata_events)))

    for channel, instrument in enumerate(PROGRAMS):
        source = [event for event in pattern.events if event.instrument == instrument]
        if not source:
            continue
        track_events = [
            (0, 0, mido.MetaMessage("track_name", name=instrument)),
            (0, 1, mido.Message("program_change", channel=channel, program=PROGRAMS[instrument])),
        ]
        for onset, stop, pitch, velocity in _rendered_notes(pattern, instrument):
            track_events.append(
                (
                    onset,
                    2,
                    mido.Message(
                        "note_on", channel=channel, note=pitch, velocity=velocity
                    ),
                )
            )
            track_events.append(
                (stop, 1, mido.Message("note_off", channel=channel, note=pitch, velocity=0))
            )
        track_events.append((final_tick, 3, mido.MetaMessage("end_of_track")))
        midi.tracks.append(mido.MidiTrack(_delta_messages(track_events)))

    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()
