from __future__ import annotations

from io import BytesIO

import mido

from app.config import PPQ

from .models import BassPattern, BassVoicePolicy


def _delta_messages(
    events: list[tuple[int, int, mido.Message | mido.MetaMessage]],
) -> list[mido.Message | mido.MetaMessage]:
    events.sort(key=lambda item: (item[0], item[1]))
    previous = 0
    result: list[mido.Message | mido.MetaMessage] = []
    for absolute, _, message in events:
        message.time = int(max(0, absolute - previous))
        previous = absolute
        result.append(message)
    return result


def _onsets_and_ends(pattern: BassPattern, channel: int) -> list[tuple[int, int, int, int]]:
    tempo = mido.bpm2tempo(pattern.bpm)
    rendered: list[list[int]] = []
    for event in pattern.events:
        micro_tick = round(mido.second2tick(event.micro_offset_us / 1_000_000, PPQ, tempo))
        onset = max(0, event.performed_tick + micro_tick)
        rendered.append([onset, onset + event.duration_tick, event.pitch, event.velocity])
    rendered.sort(key=lambda item: (item[0], item[2]))
    if pattern.voice_policy != BassVoicePolicy.ALLOW_OVERLAP:
        # Quantized/mutated events can collapse to one rendered tick after microtiming conversion.
        # Keep every note while imposing a stable, strictly ordered monophonic onset sequence.
        for previous, current in zip(rendered, rendered[1:]):
            if current[0] <= previous[0]:
                shift = previous[0] + 1 - current[0]
                current[0] += shift
                current[1] += shift
        for current, following in zip(rendered, rendered[1:]):
            current[1] = min(current[1], following[0])
            current[1] = max(current[0] + 1, current[1])
    return [(start, stop, pitch, velocity) for start, stop, pitch, velocity in rendered]


def export_bass_midi(pattern: BassPattern, channel: int = 0) -> bytes:
    if not 0 <= channel <= 15:
        raise ValueError("MIDI channel must be between 0 and 15")
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    metadata_events: list[tuple[int, int, mido.Message | mido.MetaMessage]] = [
        (0, 0, mido.MetaMessage("track_name", name="Human Bass Engine")),
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
                    f"rng={pattern.metadata.rng_algorithm}"
                ),
            ),
        ),
    ]
    for event in pattern.harmony.events:
        if event.chord:
            accidental = "#" * max(0, event.chord.root.accidental) + "b" * max(
                0, -event.chord.root.accidental
            )
            symbol = f"{event.chord.root.letter}{accidental}:{event.chord.quality.value}"
        else:
            symbol = "NO_CHORD"
        metadata_events.append((event.start_tick, 0, mido.MetaMessage("marker", text=symbol)))
    final_tick = pattern.bars * pattern.meter.bar_ticks
    metadata_events.append((final_tick, 3, mido.MetaMessage("end_of_track")))
    metadata = mido.MidiTrack(_delta_messages(metadata_events))
    midi.tracks.append(metadata)

    note_events: list[tuple[int, int, mido.Message | mido.MetaMessage]] = [
        (0, 0, mido.MetaMessage("track_name", name="bass"))
    ]
    for onset, stop, pitch, velocity in _onsets_and_ends(pattern, channel):
        note_events.append(
            (
                onset,
                2,
                mido.Message("note_on", channel=channel, note=pitch, velocity=velocity),
            )
        )
        note_events.append(
            (
                stop,
                1,
                mido.Message("note_off", channel=channel, note=pitch, velocity=0),
            )
        )
    note_final = max([final_tick, *(event[0] for event in note_events)])
    note_events.append((note_final, 3, mido.MetaMessage("end_of_track")))
    midi.tracks.append(mido.MidiTrack(_delta_messages(note_events)))

    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()
