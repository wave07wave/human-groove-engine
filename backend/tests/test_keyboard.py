from __future__ import annotations

from io import BytesIO
from statistics import mean

import mido
from fastapi.testclient import TestClient

import app.keyboard.api as keyboard_api
from app.bass.models import TempoMap, TempoSegment
from app.keyboard.generation import (
    generate_keyboard_pattern,
    profile_for_settings,
    regenerate_keyboard_pattern,
)
from app.keyboard.midi import export_keyboard_midi
from app.keyboard.models import (
    DetroitKeyboardSettings,
    KeyboardBlend,
    KeyboardEvent,
    KeyboardGenerateRequest,
    KeyboardPattern,
    KeyboardRhythmContext,
)
from app.keyboard.persistence import KeyboardDatabase
from app.main import app
from app.models.meter import MeterDefinition

HARMONY = "C | Am7 | F | G7 | C | Am7 | Dm7 | G7"


def _generated(mode: str, seed: int, *, bpm: float = 100) -> KeyboardPattern:
    return generate_keyboard_pattern(
        KeyboardGenerateRequest(
            bars=8,
            seed=seed,
            bpm=bpm,
            harmony=HARMONY,
            detroit_keyboard=DetroitKeyboardSettings(mode=mode),
        )
    )


def _averages(mode: str) -> dict[str, float]:
    patterns = [_generated(mode, seed) for seed in range(20, 40)]
    fields = (
        "onsets_per_bar",
        "syncopation_ratio",
        "mean_velocity",
        "velocity_spread",
        "timing_mean_us",
        "timing_spread_us",
        "register_mean",
        "voicing_span",
        "notes_per_onset",
        "left_hand_ratio",
        "melodic_ratio",
        "grace_ratio",
        "phrase_variation",
        "final_resolution",
    )
    return {
        field: mean(getattr(pattern.analysis, field) for pattern in patterns)
        for field in fields
    }


def test_keyboard_styles_are_deterministic_and_seeded() -> None:
    request = KeyboardGenerateRequest(
        bars=8,
        seed=8172,
        harmony=HARMONY,
        detroit_keyboard=DetroitKeyboardSettings(mode="joe"),
    )
    left = generate_keyboard_pattern(request, candidate=2)
    right = generate_keyboard_pattern(request, candidate=2)
    assert left.model_dump_json() == right.model_dump_json()

    signatures = {
        tuple(
            (event.grid_tick, tuple(event.pitches), tuple(event.velocities), event.instrument)
            for event in _generated("joe", seed).events
        )
        for seed in range(10, 20)
    }
    assert len(signatures) == 10


def test_three_keyboard_languages_have_statistically_distinct_results() -> None:
    standard = _averages("standard")
    earl = _averages("earl")
    joe = _averages("joe")
    johnny = _averages("johnny")

    assert earl["mean_velocity"] > standard["mean_velocity"] + 12
    assert earl["left_hand_ratio"] > standard["left_hand_ratio"] + 0.4
    assert earl["register_mean"] < standard["register_mean"] - 5
    assert earl["voicing_span"] > standard["voicing_span"] + 5
    assert earl["timing_mean_us"] < 0

    assert joe["onsets_per_bar"] > earl["onsets_per_bar"] + 2
    assert joe["syncopation_ratio"] > earl["syncopation_ratio"] + 0.15
    assert joe["grace_ratio"] > earl["grace_ratio"] + 0.1
    assert joe["velocity_spread"] > earl["velocity_spread"] + 3
    assert joe["timing_mean_us"] > 1_500

    assert johnny["register_mean"] > standard["register_mean"] + 10
    assert johnny["left_hand_ratio"] < standard["left_hand_ratio"]
    assert johnny["mean_velocity"] < standard["mean_velocity"] - 5
    assert johnny["melodic_ratio"] > standard["melodic_ratio"] + 0.2
    assert johnny["notes_per_onset"] < standard["notes_per_onset"] - 0.7

    assert all(
        style["final_resolution"] == 1
        for style in (standard, earl, joe, johnny)
    )


def test_blend_weights_interpolate_profiles_without_fixed_phrases() -> None:
    pure_earl = DetroitKeyboardSettings(
        mode="blend", blend=KeyboardBlend(earl=1, joe=0, johnny=0)
    )
    blended = DetroitKeyboardSettings(
        mode="blend", blend=KeyboardBlend(earl=0.2, joe=0.3, johnny=0.5)
    )
    earl_profile, _ = profile_for_settings(DetroitKeyboardSettings(mode="earl"), 100)
    pure_profile, _ = profile_for_settings(pure_earl, 100)
    blend_profile, _ = profile_for_settings(blended, 100)
    assert pure_profile == earl_profile
    assert earl_profile.register_center < blend_profile.register_center
    assert blend_profile.melodic_probability > earl_profile.melodic_probability

    signatures = {
        tuple((event.grid_tick, tuple(event.pitches)) for event in generate_keyboard_pattern(
            KeyboardGenerateRequest(seed=seed, detroit_keyboard=blended)
        ).events)
        for seed in range(6)
    }
    assert len(signatures) == 6


def test_bpm_compensation_reduces_activity_at_fast_tempos() -> None:
    medium_profile, _ = profile_for_settings(DetroitKeyboardSettings(mode="joe"), 100)
    fast_profile, _ = profile_for_settings(DetroitKeyboardSettings(mode="joe"), 180)
    assert fast_profile.density < medium_profile.density
    assert fast_profile.fill_probability < medium_profile.fill_probability
    assert fast_profile.grace_probability < medium_profile.grace_probability
    assert fast_profile.timing_spread_us < medium_profile.timing_spread_us

    medium = [_generated("joe", seed, bpm=100) for seed in range(12)]
    fast = [_generated("joe", seed, bpm=180) for seed in range(12)]
    assert mean(len(pattern.events) for pattern in fast) < mean(
        len(pattern.events) for pattern in medium
    )


def test_keyboard_styles_have_distinct_seeded_ending_behaviors() -> None:
    def ending_averages(mode: str) -> tuple[float, float, float]:
        observations: list[tuple[float, float, float]] = []
        for seed in range(120, 200):
            pattern = _generated(mode, seed)
            resolution = next(
                event for event in pattern.events if event.role == "resolution"
            )
            previous_pulse = resolution.grid_tick - pattern.meter.bar_ticks // 4
            has_pickup = any(
                previous_pulse < event.grid_tick < resolution.grid_tick
                and event.role == "fill"
                for event in pattern.events
            )
            resolution_length = resolution.duration_tick / (
                pattern.bars * pattern.meter.bar_ticks - resolution.grid_tick
            )
            ordinary_velocities = [
                mean(event.velocities)
                for event in pattern.events
                if event.role not in {"resolution", "grace"}
            ]
            resolution_lift = mean(resolution.velocities) - mean(ordinary_velocities)
            observations.append(
                (float(has_pickup), resolution_length, resolution_lift)
            )
        return tuple(
            mean(observation[index] for observation in observations)
            for index in range(3)
        )

    earl = ending_averages("earl")
    joe = ending_averages("joe")
    johnny = ending_averages("johnny")

    assert joe[0] > earl[0] + 0.25
    assert joe[0] > johnny[0] + 0.25
    assert earl[1] < joe[1] - 0.10
    assert joe[1] < johnny[1] - 0.15
    assert earl[2] > joe[2] + 4
    assert joe[2] > johnny[2] + 5


def test_rhythm_context_changes_the_keyboard_conversation() -> None:
    plain = generate_keyboard_pattern(
        KeyboardGenerateRequest(
            bars=4,
            seed=95,
            detroit_keyboard=DetroitKeyboardSettings(mode="earl"),
        )
    )
    context = KeyboardRhythmContext(
        kick_ticks=[1, 961, 1_921, 3_841, 4_801, 5_761],
        snare_ticks=[959, 2_879, 4_799, 6_719],
        bass_ticks=[2, 482, 1_922, 2_402, 3_842, 5_282],
    )
    linked = generate_keyboard_pattern(
        KeyboardGenerateRequest(
            bars=4,
            seed=95,
            detroit_keyboard=DetroitKeyboardSettings(mode="earl"),
            rhythm_context=context,
        )
    )
    assert linked.analysis.context_alignment > 0
    assert [event.grid_tick for event in linked.events] != [
        event.grid_tick for event in plain.events
    ]


def test_compound_meter_uses_a_distinct_pulse_and_resolution() -> None:
    common = {
        "bars": 1,
        "seed": 37,
        "candidate_count": 1,
        "detroit_keyboard": DetroitKeyboardSettings(mode="earl"),
    }
    three_four = generate_keyboard_pattern(
        KeyboardGenerateRequest(
            **common,
            meter=MeterDefinition.from_name("3/4"),
        )
    )
    six_eight = generate_keyboard_pattern(
        KeyboardGenerateRequest(
            **common,
            meter=MeterDefinition.from_name("6/8"),
        )
    )
    assert three_four.meter.bar_ticks == six_eight.meter.bar_ticks
    assert three_four.events != six_eight.events
    three_four_resolution = next(
        event.grid_tick for event in three_four.events if event.role == "resolution"
    )
    six_eight_resolution = next(
        event.grid_tick for event in six_eight.events if event.role == "resolution"
    )
    assert three_four_resolution == 1_920
    assert six_eight_resolution == 1_440


def test_keyboard_event_keeps_pitch_velocity_pairs_when_sorted() -> None:
    event = KeyboardEvent(
        event_id="pair-order",
        grid_tick=0,
        duration_tick=240,
        pitches=[72, 60, 67],
        velocities=[120, 40, 80],
    )
    assert event.pitches == [60, 67, 72]
    assert event.velocities == [40, 80, 120]


def test_regeneration_preserves_style_and_locked_material() -> None:
    pattern = _generated("johnny", 661)
    locked = pattern.events[0].model_copy(update={"locked": True})
    pattern.events[0] = locked
    pattern.bar_locks = [1]
    original_bar_one = [
        event.model_dump()
        for event in pattern.events
        if event.grid_tick // pattern.meter.bar_ticks == 1
    ]

    regenerated = regenerate_keyboard_pattern(pattern, {0, 1})
    assert regenerated.metadata.detroit_keyboard.mode == "johnny"
    assert regenerated.metadata.master_seed == pattern.metadata.master_seed + 1
    assert regenerated.events[0] == locked
    assert [
        event.model_dump()
        for event in regenerated.events
        if event.grid_tick // pattern.meter.bar_ticks == 1
    ] == original_bar_one


def test_regeneration_preserves_candidate_stream_and_locked_noop() -> None:
    request = KeyboardGenerateRequest(
        bars=4,
        seed=918,
        detroit_keyboard=DetroitKeyboardSettings(mode="joe"),
    )
    left = regenerate_keyboard_pattern(generate_keyboard_pattern(request, 0), set())
    right = regenerate_keyboard_pattern(generate_keyboard_pattern(request, 1), set())
    assert left.metadata.candidate_index == 0
    assert right.metadata.candidate_index == 1
    assert left.events != right.events

    locked = generate_keyboard_pattern(request, 2)
    locked.bar_locks = list(range(locked.bars))
    untouched = regenerate_keyboard_pattern(locked, set())
    assert untouched.model_dump_json() == locked.model_dump_json()


def test_repeated_regeneration_keeps_long_legacy_ids_bounded_and_deterministic() -> None:
    request = KeyboardGenerateRequest(
        bars=1,
        seed=410,
        detroit_keyboard=DetroitKeyboardSettings(mode="johnny"),
    )
    left = generate_keyboard_pattern(request)
    left.pattern_id = "legacy-" + "x" * 193
    right = left.model_copy(deep=True)
    identifiers: list[str] = []

    for revision in range(1, 56):
        left = regenerate_keyboard_pattern(left, {0})
        right = regenerate_keyboard_pattern(right, {0})
        assert left.pattern_id == right.pattern_id
        assert left.pattern_id.endswith(f"-r{revision}")
        assert len(left.pattern_id) <= 200
        identifiers.append(left.pattern_id)

    assert len(set(identifiers)) == 55
    assert left.metadata.revision == 55
    assert left.model_dump_json() == right.model_dump_json()


def test_history_saved_patterns_and_legacy_payloads(tmp_path) -> None:
    database = KeyboardDatabase(tmp_path / "keyboard.db")
    pattern = _generated("earl", 305)
    database.save_generation(pattern)
    record = database.generation_history()[0]
    restored = database.generation_record_pattern(record.generation_id)
    assert restored is not None
    assert restored.metadata.detroit_keyboard.mode == "earl"

    database.save_pattern(pattern)
    assert database.saved_patterns()[0].metadata.detroit_keyboard.mode == "earl"
    assert database.delete_pattern(pattern.pattern_id) is True

    legacy = pattern.model_dump(mode="json")
    legacy["metadata"].pop("detroit_keyboard")
    assert KeyboardPattern.model_validate(legacy).metadata.detroit_keyboard.mode == "standard"
    assert KeyboardGenerateRequest().detroit_keyboard.mode == "standard"

    same_seed_other_style = _generated("joe", 305)
    assert same_seed_other_style.pattern_id != pattern.pattern_id
    database.save_pattern(pattern)
    database.save_pattern(same_seed_other_style)
    assert len(database.saved_patterns()) == 2


def test_generation_batches_are_bounded_and_single_save_stays_compatible(tmp_path) -> None:
    database = KeyboardDatabase(
        tmp_path / "bounded-history.db", generation_history_limit=3
    )
    patterns = [_generated("earl", 500 + index) for index in range(5)]

    database.save_generations(patterns[:4])
    assert [record.pattern_id for record in database.generation_history(10)] == [
        pattern.pattern_id for pattern in reversed(patterns[1:4])
    ]

    database.save_generation(patterns[4])
    assert [record.pattern_id for record in database.generation_history(10)] == [
        pattern.pattern_id for pattern in reversed(patterns[2:5])
    ]


def test_keyboard_api_and_midi_contract(tmp_path, monkeypatch) -> None:
    database = KeyboardDatabase(tmp_path / "api.db")
    saved_batches: list[list[KeyboardPattern]] = []
    save_generations = database.save_generations

    def record_batch(patterns: list[KeyboardPattern]) -> None:
        saved_batches.append(list(patterns))
        save_generations(patterns)

    monkeypatch.setattr(database, "save_generations", record_batch)
    monkeypatch.setattr(keyboard_api, "db", database)
    client = TestClient(app)
    capabilities = client.get("/api/v1/keyboard/capabilities").json()
    assert capabilities["styles"] == ["standard", "earl", "joe", "johnny", "blend"]
    assert capabilities["external_samples"] is False
    assert capabilities["source_phrases"] is False

    response = client.post(
        "/api/v1/keyboard/generate",
        json={
            "bars": 4,
            "seed": 705,
            "candidate_count": 4,
            "detroit_keyboard": {
                "mode": "blend",
                "blend": {"earl": 0.5, "joe": 0.3, "johnny": 0.2},
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("content-encoding") == "gzip"
    assert len(saved_batches) == 1
    assert len(saved_batches[0]) == 4
    pattern = KeyboardPattern.model_validate(response.json()["candidates"][0])
    assert pattern.metadata.detroit_keyboard.mode == "blend"
    assert keyboard_api.db.generation_history()[0].style == "blend"

    midi = mido.MidiFile(file=BytesIO(export_keyboard_midi(pattern)))
    text = " ".join(
        message.text
        for track in midi.tracks
        for message in track
        if message.type == "text"
    )
    assert "detroit_keyboard=blend" in text
    assert "blend=0.5000,0.3000,0.2000" in text
    assert any(message.type == "program_change" for track in midi.tracks for message in track)

    invalid = client.post(
        "/api/v1/keyboard/generate",
        json={"candidate_count": 1, "harmony": "H???"},
    )
    assert invalid.status_code == 422


def test_midi_tempo_boundaries_and_same_pitch_retriggers() -> None:
    pattern = _generated("johnny", 808)
    final_tick = pattern.bars * pattern.meter.bar_ticks
    pattern.tempo_map = TempoMap(
        segments=[
            TempoSegment(start_tick=0, bpm=100),
            TempoSegment(start_tick=pattern.meter.bar_ticks, bpm=140),
        ]
    )
    pattern.events = [
        KeyboardEvent(
            event_id="first",
            grid_tick=0,
            duration_tick=960,
            pitches=[60],
            velocities=[70],
            instrument="acoustic_piano",
        ),
        KeyboardEvent(
            event_id="retrigger",
            grid_tick=480,
            duration_tick=960,
            pitches=[60],
            velocities=[95],
            instrument="acoustic_piano",
        ),
        KeyboardEvent(
            event_id="boundary",
            grid_tick=final_tick - 1,
            micro_offset_us=25_000,
            duration_tick=1,
            pitches=[72],
            velocities=[100],
            instrument="acoustic_piano",
        ),
    ]
    midi = mido.MidiFile(file=BytesIO(export_keyboard_midi(pattern)))

    absolute = 0
    tempo_events = []
    for message in midi.tracks[0]:
        absolute += message.time
        if message.type == "set_tempo":
            tempo_events.append((absolute, round(mido.tempo2bpm(message.tempo))))
    assert tempo_events == [(0, 100), (pattern.meter.bar_ticks, 140)]

    absolute = 0
    notes = []
    for message in midi.tracks[1]:
        absolute += message.time
        if message.type in {"note_on", "note_off"}:
            notes.append((absolute, message.type, message.note))
    pitch_60 = [item for item in notes if item[2] == 60]
    assert pitch_60 == [
        (0, "note_on", 60),
        (480, "note_off", 60),
        (480, "note_on", 60),
        (1_440, "note_off", 60),
    ]
    pitch_72 = [item for item in notes if item[2] == 72]
    assert pitch_72 == [
        (final_tick - 1, "note_on", 72),
        (final_tick, "note_off", 72),
    ]
