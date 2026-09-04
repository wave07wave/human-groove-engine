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


def _delta_messages(events):
    events.sort(key=lambda item: (item[0], item[1]))
    previous = 0
    result = []
    for absolute, _, message in events:
        message.time = max(0, int(absolute - previous))
        previous = absolute
        result.append(message)
    return result


def export_keyboard_midi(pattern: KeyboardPattern) -> bytes:
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    settings = pattern.metadata.detroit_keyboard
    metadata_events = [
        (0, 0, mido.MetaMessage("track_name", name="Human Keys Engine")),
        (0, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(pattern.bpm))),
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
                    f"detroit_keyboard={settings.mode};"
                    f"blend={settings.blend.earl:.4f},{settings.blend.joe:.4f},"
                    f"{settings.blend.johnny:.4f}"
                ),
            ),
        ),
    ]
    final_tick = pattern.bars * pattern.meter.bar_ticks
    metadata_events.append((final_tick, 3, mido.MetaMessage("end_of_track")))
    midi.tracks.append(mido.MidiTrack(_delta_messages(metadata_events)))

    tempo = mido.bpm2tempo(pattern.bpm)
    for channel, instrument in enumerate(PROGRAMS):
        source = [event for event in pattern.events if event.instrument == instrument]
        if not source:
            continue
        track_events = [
            (0, 0, mido.MetaMessage("track_name", name=instrument)),
            (0, 1, mido.Message("program_change", channel=channel, program=PROGRAMS[instrument])),
        ]
        for event in source:
            micro_tick = round(
                mido.second2tick(event.micro_offset_us / 1_000_000, PPQ, tempo)
            )
            onset = max(0, event.grid_tick + micro_tick)
            stop = min(final_tick, onset + event.duration_tick)
            for pitch, velocity in zip(event.pitches, event.velocities, strict=True):
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
