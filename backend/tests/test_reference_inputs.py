import base64
from io import BytesIO
from statistics import mean

import mido
import pytest
from fastapi.testclient import TestClient

from app.engine.generator import generate_pattern
from app.engine.phrase import tension_curve
from app.main import app
from app.models.event import EventRole
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.models.reference import (
    IntentTransformRequest,
    MidiReferenceRequest,
    TapAnalyzeRequest,
)
from app.reference import analyze_midi_reference, analyze_taps, transform_intent


def midi_payload() -> bytes:
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.extend(
        [
            mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(100), time=0),
            mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0),
            mido.Message("note_on", channel=9, note=36, velocity=112, time=0),
            mido.Message("note_on", channel=9, note=42, velocity=74, time=120),
            mido.Message("note_on", channel=9, note=38, velocity=105, time=360),
            mido.Message("note_on", channel=9, note=42, velocity=68, time=240),
            mido.MetaMessage("end_of_track", time=960),
        ]
    )
    midi.tracks.append(track)
    output = BytesIO()
    midi.save(file=output)
    return output.getvalue()


def test_taps_estimate_tempo_stability_and_alternating_feel():
    steady = analyze_taps(
        TapAnalyzeRequest(timestamps_ms=[0, 500, 1_000, 1_500, 2_000, 2_500])
    )
    alternating = analyze_taps(
        TapAnalyzeRequest(timestamps_ms=[0, 400, 1_000, 1_400, 2_000, 2_400])
    )
    assert steady.bpm == pytest.approx(120)
    assert steady.timing_stability == pytest.approx(1)
    assert alternating.alternating_feel > steady.alternating_feel
    assert alternating.suggested_intent.target_dna.swing > steady.suggested_intent.target_dna.swing


def test_midi_reference_is_parsed_in_memory_and_suggests_intent():
    request = MidiReferenceRequest(
        filename="drums.mid",
        midi_base64=base64.b64encode(midi_payload()).decode(),
    )
    result = analyze_midi_reference(request)
    assert result.filename == "drums.mid"
    assert result.bpm == pytest.approx(100)
    assert result.meter == MeterDefinition.from_name("4/4")
    assert result.hit_count == 4
    assert result.suggested_intent != request.current_intent


def test_language_transform_reports_exact_changes_and_ignores_unknown_text():
    current = GrooveIntent()
    changed = transform_intent("もっと跳ねて、ファンキーに", current)
    assert changed.suggested_style == "Funk"
    assert changed.intent.target_dna.swing > current.target_dna.swing
    assert changed.intent.target_dna.interlock > current.target_dna.interlock
    assert {change.dimension for change in changed.changes} >= {"swing", "interlock"}
    unknown = transform_intent("青い月のように", current)
    assert unknown.intent == current
    assert unknown.changes == [] and unknown.confidence == 0


def test_phrase_energy_curve_is_interpolated_and_changes_bar_energy():
    assert tension_curve(4, 0.4, 0.3, [0, 1]) == pytest.approx([0, 1 / 3, 2 / 3, 1])
    with pytest.raises(ValueError):
        GrooveIntent(phrase_energy_curve=[0.5])
    intent = GrooveIntent(phrase_energy_curve=[0.1, 0.95, 0.1, 0.95])
    pattern = generate_pattern(
        bpm=105,
        bars=4,
        meter=MeterDefinition.from_name("4/4"),
        intent=intent,
        seed=99,
        performance_mode="rule",
    )
    bar_velocities = []
    for bar in range(4):
        velocities = [
            event.velocity
            for event in pattern.events
            if event.grid_tick // pattern.meter.bar_ticks == bar
            and event.primary_role != EventRole.GHOST
        ]
        bar_velocities.append(mean(velocities))
    assert mean([bar_velocities[1], bar_velocities[3]]) > mean(
        [bar_velocities[0], bar_velocities[2]]
    )


def test_reference_api_validates_payloads_and_advertises_inputs():
    client = TestClient(app)
    taps = client.post(
        "/api/v1/reference/taps",
        json={"timestamps_ms": [0, 500, 1_000, 1_500]},
    )
    assert taps.status_code == 200 and taps.json()["bpm"] == pytest.approx(120)
    midi = client.post(
        "/api/v1/reference/midi",
        json={
            "filename": "api.mid",
            "midi_base64": base64.b64encode(midi_payload()).decode(),
        },
    )
    assert midi.status_code == 200 and midi.json()["hit_count"] == 4
    malformed = client.post(
        "/api/v1/reference/midi",
        json={"filename": "bad.mid", "midi_base64": "not-base64"},
    )
    assert malformed.status_code == 422
    transformed = client.post(
        "/api/v1/intent/transform",
        json=IntentTransformRequest(text="タイトに").model_dump(mode="json"),
    )
    assert transformed.status_code == 200
    capabilities = client.get("/api/v1/capabilities").json()
    assert capabilities["tap_to_groove"] is True
    assert capabilities["midi_reference_analysis"] is True
    assert capabilities["phrase_energy_curve"] is True
