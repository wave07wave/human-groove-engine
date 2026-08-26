from io import BytesIO

import mido
import pytest
from conftest import intent, meter

from app.engine.generator import generate_pattern
from app.midi.exporter import export_midi


@pytest.mark.parametrize(
    "meter_name,numerator,denominator",
    [("5/4", 5, 4), ("5/8", 5, 8), ("6/8", 6, 8)],
)
def test_midi_type_one_round_trip_and_no_hanging_notes(
    meter_name: str, numerator: int, denominator: int
):
    pattern = generate_pattern(bpm=103, bars=4, meter=meter(meter_name), intent=intent(), seed=21)
    payload = export_midi(pattern)
    midi = mido.MidiFile(file=BytesIO(payload))
    assert midi.type == 1
    assert midi.ticks_per_beat == 960
    assert any(
        message.type == "time_signature"
        and message.numerator == numerator
        and message.denominator == denominator
        for message in midi.tracks[0]
    )
    for track in midi.tracks:
        active: dict[tuple[int, int], int] = {}
        assert all(message.time >= 0 for message in track)
        for message in track:
            if message.type == "note_on" and message.velocity > 0:
                key = (message.channel, message.note)
                active[key] = active.get(key, 0) + 1
            elif message.type == "note_off" or (
                message.type == "note_on" and message.velocity == 0
            ):
                key = (message.channel, message.note)
                active[key] = max(0, active.get(key, 0) - 1)
        assert not any(active.values())
