from __future__ import annotations

from statistics import mean

import pytest

from app.engine import generator
from app.engine.pulse import metric_gravity
from app.engine.rhythm_language import phrase_rhythm_figure
from app.models.event import InstrumentID
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition


@pytest.mark.parametrize("meter_name", ["4/4", "3/4", "5/4", "5/8", "6/8", "12/8"])
def test_phrase_rhythm_figures_are_valid_weak_grid_landmarks(meter_name: str) -> None:
    meter = MeterDefinition.from_name(meter_name)
    figure = phrase_rhythm_figure(meter, "A")

    assert phrase_rhythm_figure(meter, "A") == figure
    assert all(
        tick % meter.subdivision_tick == 0 and 0 <= tick < meter.bar_ticks
        for tick in (figure.call_tick, figure.answer_tick, figure.turnaround_tick)
    )
    assert metric_gravity(meter, figure.call_tick) < 0.5
    assert metric_gravity(meter, figure.answer_tick) < 0.5


def _call_answer_count(pattern, figure) -> int:
    total = 0
    for bar in range(pattern.bars):
        start = bar * pattern.meter.bar_ticks
        kick_call = any(
            event.instrument == InstrumentID.KICK
            and event.grid_tick == start + figure.call_tick
            for event in pattern.events
        )
        hat_answer = any(
            event.instrument == InstrumentID.CLOSED_HAT
            and event.grid_tick == start + figure.answer_tick
            for event in pattern.events
        )
        total += kick_call and hat_answer
    return total


def test_syncopation_adds_metered_call_and_answer_figures(monkeypatch) -> None:
    monkeypatch.setattr(generator, "choose_grammar", lambda *_: "AAAA")
    meter = MeterDefinition.from_name("4/4")
    figure = phrase_rhythm_figure(meter, "A")
    restrained = GrooveIntent()
    restrained.target_dna.syncopation = 0.05
    restrained.target_dna.motor_affordance = 0.25
    restrained.target_dna.surprise = 0.05
    expressive = GrooveIntent()
    expressive.target_dna.syncopation = 0.95
    expressive.target_dna.motor_affordance = 0.95
    expressive.target_dna.surprise = 0.8
    expressive.target_dna.variation = 0.7

    low = []
    high = []
    for seed in range(20):
        low.append(
            _call_answer_count(
                generator.generate_pattern(
                    bpm=108,
                    bars=4,
                    meter=meter,
                    intent=restrained,
                    seed=seed,
                    performance_mode="rule",
                ),
                figure,
            )
        )
        high.append(
            _call_answer_count(
                generator.generate_pattern(
                    bpm=108,
                    bars=4,
                    meter=meter,
                    intent=expressive,
                    seed=seed,
                    performance_mode="rule",
                ),
                figure,
            )
        )

    assert mean(high) > mean(low) + 1
