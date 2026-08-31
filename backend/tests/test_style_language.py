from __future__ import annotations

import pytest

from app.engine.generator import generate_pattern
from app.engine.style_language import style_rhythm_profile
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
