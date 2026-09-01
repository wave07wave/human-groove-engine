from io import BytesIO

import mido
import pytest
from conftest import intent, meter

from app.engine.generator import generate_pattern
from app.midi.exporter import export_midi
from app.models.event import InstrumentID
from app.models.groove import DetroitSoulBlend, DetroitSoulSettings


def _absolute_note_messages(track: mido.MidiTrack):
    absolute = 0
    for message in track:
        absolute += message.time
        if message.type in ("note_on", "note_off"):
            yield absolute, message


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


def test_midi_explicitly_chokes_an_open_hat_with_the_next_hat_hit():
    pattern = generate_pattern(bpm=120, bars=1, meter=meter(), intent=intent(), seed=91)
    source = next(event for event in pattern.events if event.instrument == InstrumentID.KICK)
    open_hat = source.model_copy(
        update={
            "event_id": "open-long",
            "instrument": InstrumentID.OPEN_HAT,
            "grid_tick": 0,
            "structural_offset_tick": 0,
            "micro_offset_us": 0,
            "duration_tick": 2_000,
            "pitch": 46,
            "choke_group": "hihat",
        }
    )
    closed_hat = source.model_copy(
        update={
            "event_id": "closed-choke",
            "instrument": InstrumentID.CLOSED_HAT,
            "grid_tick": 480,
            "structural_offset_tick": 0,
            "micro_offset_us": 0,
            "duration_tick": 120,
            "pitch": 42,
            "choke_group": "hihat",
        }
    )
    pattern.events = [open_hat, closed_hat]

    midi = mido.MidiFile(file=BytesIO(export_midi(pattern)))
    open_track = next(
        track
        for track in midi.tracks
        if any(message.type == "track_name" and message.name == "open_hat" for message in track)
    )
    note_off_tick = next(
        absolute
        for absolute, message in _absolute_note_messages(open_track)
        if message.type == "note_off" and message.note == 46
    )
    assert note_off_tick == 480


def test_midi_metadata_preserves_detroit_soul_style_and_blend():
    pattern = generate_pattern(
        bpm=105,
        bars=2,
        meter=meter(),
        intent=intent(),
        seed=313,
        style="Funk",
        performance_mode="rule",
        detroit_soul=DetroitSoulSettings(
            mode="blend",
            blend=DetroitSoulBlend(benny=0.5, pistol=0.3, uriel=0.2),
        ),
    )
    midi = mido.MidiFile(file=BytesIO(export_midi(pattern)))
    text = " ".join(message.text for message in midi.tracks[0] if message.type == "text")

    assert "detroit_soul=blend" in text
    assert "detroit_blend=0.5000,0.3000,0.2000" in text
