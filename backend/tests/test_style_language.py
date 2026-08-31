from __future__ import annotations

import pytest

from app.engine.generator import generate_pattern
from app.engine.style_language import style_hat_profile, style_hat_variants, style_rhythm_profile
from app.models.event import InstrumentID
from app.models.meter import MeterDefinition
from app.presets import PRESETS


@pytest.mark.parametrize(
    ("style", "instrument"),
    [
        ("House", InstrumentID.KICK),
        ("Rock", InstrumentID.CLOSED_HAT),
        ("Hip Hop", InstrumentID.KICK),
    ],
)
def test_genre_styles_add_their_structural_landmarks(style: str, instrument: InstrumentID) -> None:
    meter = MeterDefinition.from_name("4/4")
    profile = style_rhythm_profile(style, meter)
    expected = (
        profile.forced_kick_ticks
        if instrument == InstrumentID.KICK
        else profile.reinforced_hat_ticks
    )
    pattern = generate_pattern(
        bpm=112,
        bars=2,
        meter=meter,
        intent=PRESETS[style],
        seed=2501,
        style=style,
        performance_mode="rule",
    )
    positions = {
        event.grid_tick % meter.bar_ticks
        for event in pattern.events
        if event.instrument == instrument
    }

    assert pattern.metadata.style == style
    assert set(expected) <= positions


def test_unknown_style_does_not_impose_a_hidden_genre_pattern() -> None:
    profile = style_rhythm_profile("My own pocket", MeterDefinition.from_name("4/4"))
    assert not profile.forced_kick_ticks
    assert not profile.reinforced_hat_ticks


def test_declared_style_hat_languages_create_distinct_safe_shapes() -> None:
    meter = MeterDefinition.from_name("4/4")
    styles = ("Funk", "Hip Hop", "House", "Rock")
    profiles = {style: style_hat_profile(style, meter) for style in styles}
    assert {profile.profile_id for profile in profiles.values()} == {
        "funk-16th-linear-v1",
        "hip-hop-pocket-8th-v1",
        "house-offbeat-909-v1",
        "rock-eighth-drive-v1",
    }
    compound_funk = style_hat_profile("Funk", MeterDefinition.from_name("6/8"))
    assert compound_funk.profile_id == "neutral-hat-v1"
    odd_funk = style_hat_profile("Funk", MeterDefinition.from_name("5/4"))
    assert odd_funk.profile_id == "neutral-hat-v1"

    patterns = {
        style: generate_pattern(
            bpm=112,
            bars=4,
            meter=meter,
            intent=PRESETS[style],
            seed=508,
            style=style,
            performance_mode="rule",
        )
        for style in profiles
    }
    counts = {}
    for style, pattern in patterns.items():
        closed = [event for event in pattern.events if event.instrument == InstrumentID.CLOSED_HAT]
        opened = [event for event in pattern.events if event.instrument == InstrumentID.OPEN_HAT]
        counts[style] = (len(closed), len(opened))
        assert closed or opened
        assert not {event.grid_tick for event in closed} & {event.grid_tick for event in opened}

    assert counts["Funk"][0] > counts["Hip Hop"][0]
    assert counts["House"][1] > counts["House"][0]
    assert sum(counts["Rock"]) >= sum(counts["Hip Hop"])


def test_style_hat_vocabulary_creates_many_seeded_shapes() -> None:
    """Each built-in style has several phrase-safe alternatives, not one loop."""
    meter = MeterDefinition.from_name("4/4")
    for style in ("Funk", "Hip Hop", "House", "Rock"):
        variants = style_hat_variants(style, meter)
        assert len(variants) == 4
        assert len({variant.variant_id for variant in variants}) == 4

    patterns = [
        generate_pattern(
            bpm=122,
            bars=4,
            meter=meter,
            intent=PRESETS["House"],
            seed=seed,
            style="House",
            performance_mode="rule",
        )
        for seed in range(12)
    ]
    vocabulary_sequences = {tuple(pattern.metadata.hat_variant_ids) for pattern in patterns}
    hat_shapes = {
        tuple(
            (event.instrument.value, event.grid_tick % meter.bar_ticks)
            for event in pattern.events
            if event.instrument in {InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT}
        )
        for pattern in patterns
    }

    assert all(len(pattern.metadata.hat_variant_ids) == pattern.bars for pattern in patterns)
    assert len(vocabulary_sequences) >= 8
    assert len(hat_shapes) >= 8
    balanced_variants = style_hat_variants("Balanced", meter)
    assert len(balanced_variants) == 4
    assert len({variant.variant_id for variant in balanced_variants}) == 4

    compound_variants = style_hat_variants("Funk", MeterDefinition.from_name("6/8"))
    assert compound_variants[0].variant_id == "neutral-carrier"


def test_balanced_generation_uses_multiple_vocabulary_shapes() -> None:
    meter = MeterDefinition.from_name("4/4")
    patterns = [
        generate_pattern(
            bpm=100,
            bars=4,
            meter=meter,
            intent=PRESETS["Balanced"],
            seed=seed,
            style="Balanced",
            performance_mode="rule",
        )
        for seed in range(43, 55)
    ]
    sequences = {tuple(pattern.metadata.hat_variant_ids) for pattern in patterns}

    assert len(sequences) >= 8
