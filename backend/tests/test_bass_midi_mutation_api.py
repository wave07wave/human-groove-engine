from __future__ import annotations

from io import BytesIO

import mido
from fastapi.testclient import TestClient

from app.bass.generation import generate_bass_pattern
from app.bass.midi import export_bass_midi
from app.bass.models import BassGenerateRequest, BassPreserveOptions, MutationOperation
from app.bass.mutation import _repair_onset_collisions, mutate_bass_pattern
from app.engine.generator import generate_pattern
from app.main import app
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition


def source_pattern():
    return generate_bass_pattern(
        BassGenerateRequest(harmony="Dm7 | G7 | Cmaj7 | A7", bars=4, seed=71),
        candidate=0,
    )


def test_pitch_only_regeneration_preserves_time_duration_and_ids() -> None:
    source = source_pattern()
    mutated = mutate_bass_pattern(source, {0, 2}, MutationOperation.PITCH_ONLY)
    before = [
        (
            event.event_id,
            event.grid_tick,
            event.structural_offset_tick,
            event.micro_offset_us,
            event.duration_tick,
        )
        for event in source.events
    ]
    after = [
        (
            event.event_id,
            event.grid_tick,
            event.structural_offset_tick,
            event.micro_offset_us,
            event.duration_tick,
        )
        for event in mutated.events
    ]
    assert before == after


def test_collision_repair_never_moves_fixed_event() -> None:
    original = source_pattern()
    assert len(original.events) >= 2
    result = original.model_copy(deep=True)
    moved, fixed = result.events[0], result.events[1]
    fixed_tick = fixed.grid_tick
    moved.grid_tick = fixed_tick

    _repair_onset_collisions(result, original)

    assert fixed.grid_tick == fixed_tick
    assert moved.grid_tick != fixed_tick
    assert original.events[0].grid_tick != moved.grid_tick


def test_pitch_lock_is_respected() -> None:
    source = source_pattern()
    source.events[0].locks.pitch = True
    pitch = source.events[0].pitch
    mutated = mutate_bass_pattern(source, {0}, MutationOperation.PITCH_ONLY)
    same = next(event for event in mutated.events if event.event_id == source.events[0].event_id)
    assert same.pitch == pitch


def test_request_level_preserve_options_hold_selected_fields() -> None:
    source = source_pattern()
    original = {event.event_id: event for event in source.events}
    preserved = BassPreserveOptions(
        keep_rhythm=True,
        keep_pitch=True,
        keep_duration=True,
        keep_timing=True,
    )

    mutated = mutate_bass_pattern(source, {0, 1}, MutationOperation.REGENERATE, preserved)

    for event in mutated.events:
        before = original[event.event_id]
        assert event.grid_tick == before.grid_tick
        assert event.pitch == before.pitch
        assert event.duration_tick == before.duration_tick
        assert event.structural_offset_tick == before.structural_offset_tick
        assert event.micro_offset_us == before.micro_offset_us


def test_keep_motif_and_kick_relation_preserve_their_structures() -> None:
    source = source_pattern()
    original = {event.event_id: event for event in source.events}
    preserved = BassPreserveOptions(keep_motif=True, keep_kick_relation=True)

    mutated = mutate_bass_pattern(source, set(), MutationOperation.REGENERATE, preserved)

    for event in mutated.events:
        before = original[event.event_id]
        assert event.performed_tick == before.performed_tick
        if event.motif_id:
            assert (
                event.grid_tick,
                event.pitch,
                event.duration_tick,
                event.harmonic_role,
                event.rhythmic_role,
                event.approach_target_id,
            ) == (
                before.grid_tick,
                before.pitch,
                before.duration_tick,
                before.harmonic_role,
                before.rhythmic_role,
                before.approach_target_id,
            )


def test_keep_register_shape_does_not_cross_the_preferred_center() -> None:
    source = source_pattern()
    original = {event.event_id: event for event in source.events}
    preserved = BassPreserveOptions(keep_register_shape=True)

    mutated = mutate_bass_pattern(source, set(), MutationOperation.PITCH_ONLY, preserved)

    center = source.register_limits.preferred_center
    for event in mutated.events:
        before = original[event.event_id]
        assert (event.pitch - center) * (before.pitch - center) >= 0


def test_persistent_intent_locks_apply_to_refine_and_regeneration() -> None:
    source = source_pattern()
    source.intent_locks.keep_rhythm_feel = True
    source.intent_locks.keep_register = True
    source.intent_locks.keep_kick_relationship = True
    original = {event.event_id: event for event in source.events}

    mutated = mutate_bass_pattern(source, set(), MutationOperation.REGENERATE)

    center = source.register_limits.preferred_center
    for event in mutated.events:
        before = original[event.event_id]
        assert event.grid_tick == before.grid_tick
        assert event.micro_offset_us == before.micro_offset_us
        assert event.performed_tick == before.performed_tick
        assert (event.pitch - center) * (before.pitch - center) >= 0
    assert mutated.intent_locks.model_dump() == source.intent_locks.model_dump()


def test_midi_round_trip_and_monophonic_safety() -> None:
    pattern = source_pattern()
    midi = mido.MidiFile(file=BytesIO(export_bass_midi(pattern)))
    assert midi.type == 1
    assert midi.ticks_per_beat == 960
    assert len(midi.tracks) == 2
    absolute = 0
    active: set[int] = set()
    for message in midi.tracks[1]:
        assert message.time >= 0
        absolute += message.time
        if message.type == "note_on" and message.velocity:
            assert not active
            active.add(message.note)
        elif message.type in ("note_off", "note_on"):
            active.discard(message.note)
    assert not active


def test_bass_api_contracts() -> None:
    client = TestClient(app)
    capability = client.get("/api/v1/bass/capabilities")
    assert capability.status_code == 200
    assert capability.json()["groove_context"] is True
    assert capability.json()["history_pattern_load"] is True
    assert capability.json()["preserve_options"] == [
        "rhythm",
        "pitch",
        "duration",
        "timing",
        "motif",
        "kick_relation",
        "register_shape",
    ]
    assert capability.json()["intent_locks"] == ["rhythm_feel", "register", "kick_relationship"]

    response = client.post(
        "/api/v1/bass/generate",
        json={
            "bars": 2,
            "harmony": "Dm7 | G7",
            "candidate_count": 1,
            "seed": 52,
        },
    )
    assert response.status_code == 200, response.text
    candidate = response.json()["candidates"][0]
    assert candidate["analysis"]["atomic"] != candidate["intent"]["target"]

    preserved = client.post(
        "/api/v1/bass/mutate",
        json={
            "pattern": candidate,
            "bars": [0],
            "operation": "regenerate",
            "preserve": {
                "keep_rhythm": True,
                "keep_pitch": True,
                "keep_duration": True,
                "keep_timing": True,
            },
        },
    )
    assert preserved.status_code == 200, preserved.text
    bar_ticks = (
        candidate["meter"]["numerator"] * 960 * 4 // candidate["meter"]["denominator"]
    )
    before = {
        event["event_id"]: (
            event["grid_tick"],
            event["pitch"],
            event["duration_tick"],
            event["micro_offset_us"],
        )
        for event in candidate["events"]
        if event["grid_tick"] < bar_ticks
    }
    after = {
        event["event_id"]: (
            event["grid_tick"],
            event["pitch"],
            event["duration_tick"],
            event["micro_offset_us"],
        )
        for event in preserved.json()["events"]
        if event["event_id"] in before
    }
    assert after == before

    exported = client.post("/api/v1/bass/export-midi", json=candidate)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("audio/midi")
    channel_export = client.post("/api/v1/bass/export-midi?channel=8", json=candidate)
    assert channel_export.status_code == 200
    channel_midi = mido.MidiFile(file=BytesIO(channel_export.content))
    assert any(
        message.type == "note_on" and message.channel == 8 for message in channel_midi.tracks[1]
    )
    assert client.post("/api/v1/bass/export-midi?channel=16", json=candidate).status_code == 422


def test_groove_pattern_adapts_to_versioned_bass_context() -> None:
    groove = generate_pattern(
        bpm=108,
        bars=4,
        meter=MeterDefinition.from_name("4/4"),
        intent=GrooveIntent(),
        seed=99,
    )
    response = TestClient(app).post(
        "/api/v1/bass/context/from-groove", json=groove.model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    context = response.json()
    assert context["meter"] == groove.meter.model_dump(mode="json")
    assert context["tempo_map"]["segments"][0]["bpm"] == 108
    assert len(context["kick_events"]) == sum(
        event.instrument.value == "kick" for event in groove.events
    )
    assert context["metric_gravity"]
