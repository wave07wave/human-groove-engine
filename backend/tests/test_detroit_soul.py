import hashlib
import json
from dataclasses import fields
from statistics import mean, pstdev

import pytest
from conftest import intent, meter

from app.engine.detroit_soul import PROFILES, resolve_profile
from app.engine.generator import generate_pattern
from app.engine.mutation import regenerate_selected
from app.models.event import EventRole, InstrumentID
from app.models.groove import DetroitSoulBlend, DetroitSoulSettings
from app.models.meter import MeterDefinition
from app.models.pattern import GroovePattern
from app.persistence.database import GrooveDatabase


def generate(mode: str, seed: int, *, bpm: float = 105):
    return generate_pattern(
        bpm=bpm,
        bars=4,
        meter=meter(),
        intent=intent(),
        seed=seed,
        style="Funk",
        performance_mode="rule",
        render_profile="off",
        detroit_soul=DetroitSoulSettings(mode=mode),
    )


def metrics(mode: str) -> dict[str, float]:
    rows = []
    for seed in range(40, 76):
        pattern = generate(mode, seed)
        drum_voices = {
            InstrumentID.KICK,
            InstrumentID.SNARE,
            InstrumentID.CLOSED_HAT,
            InstrumentID.OPEN_HAT,
        }
        drums = [event for event in pattern.events if event.instrument in drum_voices]
        snares = [event for event in drums if event.instrument == InstrumentID.SNARE]
        hats = [
            event
            for event in drums
            if event.instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT)
        ]
        backbeats = [
            event
            for event in snares
            if event.grid_tick % pattern.meter.bar_ticks in (960, 2_880)
        ]
        lane_dispersion = []
        for instrument in drum_voices:
            timings = [
                event.micro_offset_us for event in drums if event.instrument == instrument
            ]
            if len(timings) > 1:
                lane_dispersion.append(pstdev(timings))
        rows.append(
            {
                "timing_mean": mean(event.micro_offset_us for event in drums),
                "timing_dispersion": mean(lane_dispersion),
                "backbeat_velocity": mean(event.velocity for event in backbeats),
                "hat_velocity": mean(event.velocity for event in hats),
                "hat_count": len(hats),
                "open_hat_count": sum(
                    event.instrument == InstrumentID.OPEN_HAT for event in hats
                ),
                "kick_count": sum(
                    event.instrument == InstrumentID.KICK for event in drums
                ),
                "ghost_count": sum(
                    event.primary_role == EventRole.GHOST for event in snares
                ),
                "fill_count": sum(
                    event.primary_role == EventRole.TRANSITION for event in drums
                ),
            }
        )
    return {key: mean(row[key] for row in rows) for key in rows[0]}


@pytest.mark.parametrize("mode", ["benny", "pistol", "uriel", "blend"])
def test_style_generation_is_deterministic_and_seed_varied(mode: str):
    settings = DetroitSoulSettings(
        mode=mode,
        blend=DetroitSoulBlend(benny=0.2, pistol=0.3, uriel=0.5),
    )
    arguments = dict(
        bpm=105,
        bars=4,
        meter=meter(),
        intent=intent(),
        seed=92,
        style="Funk",
        performance_mode="rule",
        render_profile="off",
        detroit_soul=settings,
    )
    left = generate_pattern(**arguments)
    right = generate_pattern(**arguments)
    assert left.model_dump_json() == right.model_dump_json()

    signatures = {
        tuple(
            (event.instrument, event.grid_tick, event.micro_offset_us, event.velocity)
            for event in generate_pattern(**{**arguments, "seed": seed}).events
        )
        for seed in range(10, 18)
    }
    assert len(signatures) == 8


def test_standard_mode_preserves_the_existing_generator_result():
    arguments = dict(
        bpm=105,
        bars=4,
        meter=meter(),
        intent=intent(),
        seed=419,
        style="Funk",
        performance_mode="rule",
        render_profile="off",
    )
    legacy_call = generate_pattern(**arguments)
    explicit_standard = generate_pattern(
        **arguments, detroit_soul=DetroitSoulSettings(mode="standard")
    )
    assert legacy_call.model_dump_json() == explicit_standard.model_dump_json()


@pytest.mark.parametrize(
    ("style", "meter_name", "subdivisions", "bpm", "seed", "performance_mode", "expected"),
    [
        (
            "Funk",
            "4/4",
            4,
            105,
            419,
            "rule",
            "39931fb6c44419806121822c9dd9b1fad0d305f5f22a74d23ab882b61db0ba60",
        ),
        (
            "Balanced",
            "3/4",
            3,
            92,
            7,
            "rule",
            "871891b2d999bbb968742435fee6b44944a5f6d8af4efa5fff62726109bc1110",
        ),
        (
            "House",
            "6/8",
            4,
            126,
            113,
            "auto",
            "1d75f47237d48399c8e8917dbffce44d3b9c4b3594fecc9fa6168f8263230bba",
        ),
        (
            "Hip Hop",
            "5/8",
            4,
            78,
            991,
            "rule",
            "c8e1a3a3c95b740d3c7f47b3183b1c3608e8b7d2a0412534788484d0687c70d6",
        ),
        (
            "Rock",
            "12/8",
            6,
            144,
            2_048,
            "auto",
            "878bbb738b3ce227158718be81945c0908b51a49adf5023fbf9c8c509db468ed",
        ),
    ],
)
def test_standard_event_output_matches_the_pre_feature_release(
    style: str,
    meter_name: str,
    subdivisions: int,
    bpm: float,
    seed: int,
    performance_mode: str,
    expected: str,
):
    selected_meter = MeterDefinition.model_validate(
        meter(meter_name)
        .model_copy(update={"subdivisions_per_quarter": subdivisions})
        .model_dump()
    )
    pattern = generate_pattern(
        bpm=bpm,
        bars=4,
        meter=selected_meter,
        intent=intent(),
        seed=seed,
        style=style,
        performance_mode=performance_mode,
        render_profile="off",
    )
    payload = json.dumps(
        [event.model_dump(mode="json") for event in pattern.events],
        sort_keys=True,
        separators=(",", ":"),
    )

    assert hashlib.sha256(payload.encode()).hexdigest() == expected


def test_three_profiles_have_expected_statistical_differences_across_seeds():
    benny = metrics("benny")
    pistol = metrics("pistol")
    uriel = metrics("uriel")

    assert benny["timing_mean"] < -1_000
    assert uriel["timing_mean"] > 1_500
    assert benny["timing_dispersion"] < pistol["timing_dispersion"] * 0.55
    assert benny["timing_dispersion"] < uriel["timing_dispersion"] * 0.7
    assert pistol["backbeat_velocity"] > benny["backbeat_velocity"] + 5
    assert uriel["backbeat_velocity"] > pistol["backbeat_velocity"]
    assert pistol["hat_velocity"] > benny["hat_velocity"] + 7
    assert pistol["hat_velocity"] > uriel["hat_velocity"] + 12
    assert pistol["open_hat_count"] > uriel["open_hat_count"] + 3
    assert uriel["hat_count"] < benny["hat_count"] * 0.82
    assert uriel["kick_count"] < benny["kick_count"] * 0.82
    assert uriel["ghost_count"] > benny["ghost_count"] + 1
    assert benny["fill_count"] > uriel["fill_count"] + 2


def test_blend_normalizes_influences_and_interpolates_every_profile_parameter():
    weights = {"benny": 0.6, "pistol": 0.3, "uriel": 0.1}
    profile = resolve_profile(
        DetroitSoulSettings(mode="blend", blend=DetroitSoulBlend(**weights))
    )

    assert profile is not None
    for field in fields(profile):
        expected = sum(
            getattr(PROFILES[name], field.name) * weight
            for name, weight in weights.items()
        )
        assert getattr(profile, field.name) == pytest.approx(expected)


def test_drummer_layer_operates_independently_of_genre_preset():
    for style in ("Balanced", "Funk", "Hip Hop", "House", "Rock"):
        arguments = dict(
            bpm=105,
            bars=2,
            meter=meter(),
            intent=intent(),
            seed=280,
            style=style,
            performance_mode="rule",
            render_profile="off",
        )
        standard = generate_pattern(**arguments)
        styled = generate_pattern(
            **arguments, detroit_soul=DetroitSoulSettings(mode="pistol")
        )

        assert styled.metadata.style == style
        assert styled.metadata.detroit_soul.mode == "pistol"
        assert styled.events != standard.events


def test_blend_and_partial_regeneration_preserve_settings():
    settings = DetroitSoulSettings(
        mode="blend",
        blend=DetroitSoulBlend(benny=0.55, pistol=0.3, uriel=0.15),
    )
    pattern = generate_pattern(
        bpm=105,
        bars=4,
        meter=meter(),
        intent=intent(),
        seed=512,
        style="Funk",
        performance_mode="rule",
        render_profile="off",
        detroit_soul=settings,
    )
    regenerated = regenerate_selected(pattern, {InstrumentID.SNARE}, {3})

    assert pattern.metadata.detroit_soul == settings
    assert regenerated.metadata.detroit_soul == settings


def test_generation_persistence_round_trip_preserves_style_settings(tmp_path):
    settings = DetroitSoulSettings(
        mode="blend",
        blend=DetroitSoulBlend(benny=0.15, pistol=0.55, uriel=0.3),
    )
    pattern = generate_pattern(
        bpm=105,
        bars=2,
        meter=meter(),
        intent=intent(),
        seed=614,
        style="Funk",
        performance_mode="rule",
        render_profile="off",
        detroit_soul=settings,
    )
    database = GrooveDatabase(tmp_path / "detroit-history.db")
    database.save_generation(pattern)
    with database.connect() as connection:
        payload = connection.execute(
            "SELECT payload FROM generations WHERE pattern_id=? ORDER BY id DESC LIMIT 1",
            (pattern.pattern_id,),
        ).fetchone()["payload"]
    restored = GroovePattern.model_validate_json(payload)

    assert restored.metadata.detroit_soul == settings


@pytest.mark.parametrize("mode", ["benny", "pistol", "uriel"])
def test_phrase_end_raises_style_generated_fill_probability(mode: str):
    additions_by_bar = [0, 0, 0, 0]
    for seed in range(40, 104):
        standard = generate("standard", seed)
        styled = generate(mode, seed)
        standard_ids = {event.event_id for event in standard.events}
        for event in styled.events:
            if (
                event.event_id not in standard_ids
                and event.primary_role == EventRole.TRANSITION
            ):
                additions_by_bar[event.grid_tick // styled.meter.bar_ticks] += 1

    non_ending_mean = mean(additions_by_bar[:3])
    assert additions_by_bar[3] > non_ending_mean * 1.5


def test_tempo_compensation_reduces_fast_hat_density():
    slow_counts = []
    fast_counts = []
    for seed in range(12):
        for bpm, target in ((76, slow_counts), (168, fast_counts)):
            pattern = generate("pistol", seed, bpm=bpm)
            target.append(
                sum(
                    event.instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT)
                    for event in pattern.events
                )
            )
    assert mean(fast_counts) < mean(slow_counts) * 0.9


def test_all_supported_meter_grids_keep_generated_style_events_on_grid():
    for meter_name in ("4/4", "3/4", "5/4", "5/8", "6/8", "12/8"):
        base_meter = meter(meter_name)
        for subdivisions in range(1, 17):
            try:
                grid_meter = MeterDefinition.model_validate(
                    base_meter.model_copy(
                        update={"subdivisions_per_quarter": subdivisions}
                    ).model_dump()
                )
            except ValueError:
                continue
            for mode in ("benny", "pistol", "uriel", "blend"):
                pattern = generate_pattern(
                    bpm=105,
                    bars=2,
                    meter=grid_meter,
                    intent=intent(),
                    seed=23,
                    style="Funk",
                    performance_mode="rule",
                    render_profile="off",
                    detroit_soul=DetroitSoulSettings(mode=mode),
                )
                assert all(
                    event.grid_tick % grid_meter.subdivision_tick == 0
                    for event in pattern.events
                ), (meter_name, subdivisions, mode)


def test_drummer_layer_preserves_bass_performance_and_removes_only_orphan_confirmations():
    arguments = dict(
        bpm=105,
        bars=4,
        meter=meter(),
        intent=intent(),
        seed=40,
        style="Funk",
        performance_mode="rule",
        render_profile="off",
    )
    standard = generate_pattern(**arguments)
    uriel = generate_pattern(
        **arguments, detroit_soul=DetroitSoulSettings(mode="uriel")
    )
    original_bass = {
        event.event_id: event.model_dump()
        for event in standard.events
        if event.instrument == InstrumentID.BASS
    }
    final_kicks = {
        event.grid_tick
        for event in uriel.events
        if event.instrument == InstrumentID.KICK
    }
    styled_bass = [
        event for event in uriel.events if event.instrument == InstrumentID.BASS
    ]

    assert all(event.model_dump() == original_bass[event.event_id] for event in styled_bass)
    assert all(
        event.primary_role != EventRole.CONFIRMATION or event.grid_tick in final_kicks
        for event in styled_bass
    )


def test_kick_snare_coordination_changes_seeded_response_frequency():
    near_responses: dict[str, list[int]] = {"benny": [], "uriel": []}
    for seed in range(40, 64):
        standard = generate("standard", seed)
        base_kicks = {
            event.grid_tick
            for event in standard.events
            if event.instrument == InstrumentID.KICK
        }
        for mode in near_responses:
            pattern = generate(mode, seed)
            backbeats = [
                event.grid_tick
                for event in pattern.events
                if event.instrument == InstrumentID.SNARE
                and event.primary_role == EventRole.ANCHOR
            ]
            added_kicks = [
                event.grid_tick
                for event in pattern.events
                if event.instrument == InstrumentID.KICK
                and event.grid_tick not in base_kicks
            ]
            near_responses[mode].append(
                sum(
                    min(
                        (abs(tick - backbeat) for backbeat in backbeats),
                        default=10_000,
                    )
                    <= 2 * pattern.meter.subdivision_tick
                    for tick in added_kicks
                )
            )

    assert mean(near_responses["benny"]) > mean(near_responses["uriel"]) + 1
