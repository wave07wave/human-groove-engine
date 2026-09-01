from __future__ import annotations

from io import BytesIO

import mido

from app.config import PPQ
from app.models.event import InstrumentID
from app.models.pattern import GroovePattern


def _to_delta(
    events: list[tuple[int, int, mido.Message | mido.MetaMessage]],
) -> list[mido.Message | mido.MetaMessage]:
    events.sort(key=lambda item: (item[0], item[1]))
    previous = 0
    result = []
    for absolute, _, message in events:
        message.time = max(0, int(absolute - previous))
        previous = absolute
        result.append(message)
    return result


def _performed_onset(event, tempo: int) -> int:
    micro_ticks = int(round(mido.second2tick(event.micro_offset_us / 1_000_000, PPQ, tempo)))
    return max(0, event.performed_tick + micro_ticks)


def _open_hat_choke_ends(pattern: GroovePattern, tempo: int) -> dict[str, int]:
    """Return the absolute end tick for each open-hat hit cut by a later hat.

    MIDI puts open and closed hats on separate notes, so General MIDI devices
    do not reliably infer an acoustic choke from the later closed-hat note.
    We write the corresponding open-hat note-off explicitly.
    """
    hat_events = sorted(
        (
            (_performed_onset(event, tempo), event)
            for event in pattern.events
            if event.choke_group == "hihat"
            and event.instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT)
        ),
        key=lambda item: (item[0], item[1].event_id),
    )
    choke_ends: dict[str, int] = {}
    active_open: tuple[int, str] | None = None
    for onset, event in hat_events:
        if active_open is not None and onset > active_open[0]:
            choke_ends[active_open[1]] = onset
            active_open = None
        if event.instrument == InstrumentID.OPEN_HAT:
            active_open = (onset, event.event_id)
    return choke_ends


def export_midi(pattern: GroovePattern) -> bytes:
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    tempo = mido.bpm2tempo(pattern.bpm)
    open_hat_choke_ends = _open_hat_choke_ends(pattern, tempo)
    metadata = mido.MidiTrack()
    detroit = pattern.metadata.detroit_soul
    detroit_metadata = f"detroit_soul={detroit.mode}"
    if detroit.mode == "blend":
        detroit_metadata += (
            f";detroit_blend={detroit.blend.benny:.4f},"
            f"{detroit.blend.pistol:.4f},{detroit.blend.uriel:.4f}"
        )
    metadata.extend(
        _to_delta(
            [
                (0, 0, mido.MetaMessage("track_name", name="Human Groove Engine")),
                (0, 0, mido.MetaMessage("set_tempo", tempo=tempo)),
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
                            f"engine={pattern.metadata.engine_version};schema={pattern.metadata.schema_version};"
                            f"seed={pattern.metadata.master_seed};rng={pattern.metadata.rng_algorithm};"
                            f"{detroit_metadata}"
                        ),
                    ),
                ),
                (pattern.bars * pattern.meter.bar_ticks, 3, mido.MetaMessage("end_of_track")),
            ]
        )
    )
    midi.tracks.append(metadata)

    grouped: dict[InstrumentID, list] = {instrument: [] for instrument in InstrumentID}
    for event in pattern.events:
        grouped[event.instrument].append(event)
    for instrument, source_events in grouped.items():
        if not source_events:
            continue
        track = mido.MidiTrack()
        absolute_messages: list[tuple[int, int, mido.Message | mido.MetaMessage]] = [
            (0, 0, mido.MetaMessage("track_name", name=instrument.value))
        ]
        channel = 0 if instrument == InstrumentID.BASS else 9
        timed = []
        for event in source_events:
            timed.append((_performed_onset(event, tempo), event))
        timed.sort(key=lambda item: (item[0], item[1].event_id))
        for index, (onset, event) in enumerate(timed):
            pitch = event.pitch if event.pitch is not None else 36
            next_same_pitch = next(
                (
                    future_onset
                    for future_onset, future in timed[index + 1 :]
                    if (future.pitch if future.pitch is not None else 36) == pitch
                ),
                None,
            )
            natural_end = onset + event.duration_tick
            choke_end = open_hat_choke_ends.get(event.event_id)
            if choke_end is not None:
                natural_end = min(natural_end, choke_end)
            end = max(
                onset + 1, min(natural_end, next_same_pitch) if next_same_pitch else natural_end
            )
            absolute_messages.append(
                (
                    onset,
                    2,
                    mido.Message("note_on", channel=channel, note=pitch, velocity=event.velocity),
                )
            )
            absolute_messages.append(
                (end, 1, mido.Message("note_off", channel=channel, note=pitch, velocity=0))
            )
        final_tick = max(
            [pattern.bars * pattern.meter.bar_ticks, *(x[0] for x in absolute_messages)]
        )
        absolute_messages.append((final_tick, 3, mido.MetaMessage("end_of_track")))
        track.extend(_to_delta(absolute_messages))
        midi.tracks.append(track)
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()
