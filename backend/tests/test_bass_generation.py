from __future__ import annotations

from statistics import mean

import pytest

from app.bass.generation import generate_bass_candidates, generate_bass_pattern
from app.bass.models import (
    BassGenerateRequest,
    BassIntent,
    GrooveContext,
    InputMode,
    KickEvent,
    ScaleMode,
    TempoMap,
)
from app.models.meter import MeterDefinition


def generated(**changes) -> object:
    return generate_bass_pattern(BassGenerateRequest(**changes), candidate=0)


def test_generation_is_exactly_deterministic() -> None:
    request = BassGenerateRequest(harmony="Dm7 | G7 | Cmaj7 | A7", bars=8, seed=9081)
    left = generate_bass_pattern(request, candidate=2)
    right = generate_bass_pattern(request, candidate=2)
    assert left.model_dump_json() == right.model_dump_json()


@pytest.mark.parametrize("input_mode", list(InputMode))
def test_generation_preserves_input_mode_for_persistence(input_mode: InputMode) -> None:
    pattern = generated(input_mode=input_mode, harmony="C | G", key="C")
    assert pattern.input_mode == input_mode


@pytest.mark.parametrize("meter_name", ["4/4", "3/4", "6/8", "12/8"])
def test_meter_generation_invariants(meter_name: str) -> None:
    pattern = generated(bars=4, meter=MeterDefinition.from_name(meter_name))
    assert pattern.events
    assert all(
        0 <= event.grid_tick < pattern.bars * pattern.meter.bar_ticks for event in pattern.events
    )
    assert all(event.duration_tick > 0 for event in pattern.events)


def test_root_strength_has_a_measured_effect() -> None:
    low, high = BassIntent(), BassIntent()
    low.target.root_strength = 0
    high.target.root_strength = 1
    low_values = [generated(seed=seed, intent=low).analysis.atomic.root_ratio for seed in range(5)]
    high_values = [
        generated(seed=seed, intent=high).analysis.atomic.root_ratio for seed in range(5)
    ]
    assert mean(high_values) > mean(low_values) + 0.35


def test_density_and_silence_are_measured_separately() -> None:
    sparse, dense = BassIntent(), BassIntent()
    sparse.target.density = 0
    dense.target.density = 1
    low_counts = [len(generated(seed=seed, intent=sparse).events) for seed in range(4)]
    high_counts = [len(generated(seed=seed, intent=dense).events) for seed in range(4)]
    assert mean(high_counts) > mean(low_counts)

    connected, spacious = BassIntent(), BassIntent()
    connected.target.silence = 0
    spacious.target.silence = 1
    connected_occupancy = [
        generated(seed=seed, intent=connected).analysis.atomic.active_occupancy for seed in range(4)
    ]
    spacious_occupancy = [
        generated(seed=seed, intent=spacious).analysis.atomic.active_occupancy for seed in range(4)
    ]
    assert mean(spacious_occupancy) < mean(connected_occupancy)


def test_chromatic_off_and_directed_chromatic_targets() -> None:
    off = BassIntent(allow_chromatic_notes=False)
    off.target.chromaticism = 1
    stable = generated(harmony="Dm7 | G7 | Cmaj7 | A7", bars=8, seed=4, intent=off)
    assert stable.analysis.atomic.chromatic_ratio == 0

    active = BassIntent()
    active.target.chromaticism = 1
    active.target.approach_activity = 1
    patterns = [
        generated(harmony="Dm7 | G7 | Cmaj7 | A7", bars=8, seed=seed, intent=active)
        for seed in range(4)
    ]
    approaches = [
        event for pattern in patterns for event in pattern.events if event.approach_target_id
    ]
    assert approaches
    for pattern in patterns:
        ids = {event.event_id for event in pattern.events}
        assert all(
            event.approach_target_id in ids for event in pattern.events if event.approach_target_id
        )


def test_kick_lock_target_increases_proximity() -> None:
    meter = MeterDefinition.from_name("4/4")
    context = GrooveContext(
        tempo_map=TempoMap(),
        meter=meter,
        kick_events=[
            KickEvent(grid_tick=bar * meter.bar_ticks + beat * 960)
            for bar in range(4)
            for beat in range(4)
        ],
    )
    low, high = BassIntent(), BassIntent()
    low.target.kick_lock, low.target.kick_complement = 0, 1
    high.target.kick_lock, high.target.kick_complement = 1, 0
    low_scores = [
        generated(seed=seed, intent=low, groove_context=context).analysis.atomic.kick_lock_ratio
        for seed in range(5)
    ]
    high_scores = [
        generated(seed=seed, intent=high, groove_context=context).analysis.atomic.kick_lock_ratio
        for seed in range(5)
    ]
    assert mean(high_scores) > mean(low_scores)


def test_no_harmony_mode_and_long_form_generation() -> None:
    modal = generated(
        bars=16,
        input_mode=InputMode.KEY_MODE,
        key="D",
        mode=ScaleMode.DORIAN,
        harmony="ignored",
    )
    assert modal.events
    assert all(event.chord is None for event in modal.harmony.events)

    long_form = generated(bars=64, harmony="Cmaj7", seed=23)
    assert long_form.events
    bar_signatures = {
        tuple(
            (event.grid_tick % long_form.meter.bar_ticks, event.pitch % 12)
            for event in long_form.events
            if event.grid_tick // long_form.meter.bar_ticks == bar
        )
        for bar in range(long_form.bars)
    }
    assert len(bar_signatures) > 4


def test_four_candidates_are_fitness_selected_and_diverse() -> None:
    candidates = generate_bass_candidates(BassGenerateRequest(harmony="Am7 | D7", bars=8, seed=81))
    assert len(candidates) == 4
    assert len({candidate.model_dump_json() for candidate in candidates}) == 4
    assert all(candidate.analysis is not None for candidate in candidates)
