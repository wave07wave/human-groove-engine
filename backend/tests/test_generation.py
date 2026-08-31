import pytest
from conftest import intent, meter

from app.analysis.listener import analyze_pattern
from app.engine.generator import generate_pattern
from app.engine.mutation import regenerate_selected
from app.engine.optimizer import (
    generate_candidate_pool,
    generate_candidates,
    pattern_distance,
    preference_guided_groove_intent,
)
from app.models.event import InstrumentID
from app.models.meter import MeterDefinition
from app.models.preference import GroovePreferenceRange, GroovePreferenceSummary


def make(seed=42, groove_intent=None, meter_name="4/4", bars=4):
    return generate_pattern(
        bpm=105,
        bars=bars,
        meter=meter(meter_name),
        intent=groove_intent or intent(),
        seed=seed,
    )


def strong_groove_preference() -> GroovePreferenceSummary:
    return GroovePreferenceSummary(
        comparisons=25,
        decisive_comparisons=25,
        effective_comparisons=25,
        learning_confidence=1,
        personal_weight=0.8,
        feature_weights={"density": 1},
        preferred_ranges={
            "density": GroovePreferenceRange(
                mean=0.65,
                low=0.55,
                high=0.75,
                uncertainty=0,
                observations=25,
                evidence=1,
            )
        },
    )


def test_generation_is_fully_deterministic():
    left = make()
    right = make()
    assert left.model_dump_json() == right.model_dump_json()


def test_all_events_are_valid_and_phrase_has_pulse_carrier():
    for meter_name in ("4/4", "3/4", "5/4", "5/8", "6/8", "12/8"):
        pattern = make(meter_name=meter_name)
        end = pattern.bars * pattern.meter.bar_ticks
        assert any(event.instrument == InstrumentID.KICK for event in pattern.events)
        assert all(0 <= event.performed_tick < end for event in pattern.events)
        assert all(
            1 <= event.velocity <= 127 and event.duration_tick > 0 for event in pattern.events
        )
        analysis = analyze_pattern(pattern)
        values = analysis.measured_dna.model_dump().values()
        assert all(0 <= value <= 1 for value in values)


def test_partial_regeneration_preserves_other_instruments():
    original = make()
    changed = regenerate_selected(original, {InstrumentID.BASS}, {2})
    before = [
        e.model_dump()
        for e in original.events
        if e.instrument != InstrumentID.BASS or e.grid_tick // original.meter.bar_ticks != 2
    ]
    after = [
        e.model_dump()
        for e in changed.events
        if e.instrument != InstrumentID.BASS or e.grid_tick // changed.meter.bar_ticks != 2
    ]
    assert before == after


def test_event_and_instrument_locks_are_invariant():
    original = make()
    original.instrument_locks.add(InstrumentID.KICK)
    bass_event = next(e for e in original.events if e.instrument == InstrumentID.BASS)
    bass_event.locked = True
    changed = regenerate_selected(original, {InstrumentID.KICK, InstrumentID.BASS}, set(range(4)))
    assert [e.model_dump() for e in original.events if e.instrument == InstrumentID.KICK] == [
        e.model_dump() for e in changed.events if e.instrument == InstrumentID.KICK
    ]
    assert bass_event.model_dump() in [e.model_dump() for e in changed.events]


def test_optimizer_returns_four_meaningfully_distinct_candidates():
    result = generate_candidates(bpm=100, bars=4, meter=meter(), intent=intent(), seed=17)
    assert len(result) == 4
    assert len({item.pattern_id for item in result}) == 4
    assert min(pattern_distance(a, b) for i, a in enumerate(result) for b in result[i + 1 :]) > 0.02
    assert all(item.analysis is not None for item in result)


def test_target_and_measured_dna_are_separate_values():
    pattern = make(groove_intent=intent(syncopation=0.95))
    pattern.analysis = analyze_pattern(pattern)
    assert pattern.intent.target_dna is not pattern.analysis.measured_dna
    assert pattern.analysis.measured_dna.syncopation != 0.95


def test_preference_guidance_moves_only_the_private_search_intent() -> None:
    requested = intent(density=0.1)
    guided, guidance = preference_guided_groove_intent(
        requested, strong_groove_preference()
    )

    assert requested.target_dna.density == 0.1
    assert guided.target_dna.density == pytest.approx(0.2925)
    assert guidance.features == ("density",)


def test_candidate_pool_mixes_normal_and_preference_guided_search() -> None:
    requested = intent(density=0.1)
    pool = generate_candidate_pool(
        bpm=100,
        bars=1,
        meter=meter(),
        intent=requested,
        seed=1701,
        performance_mode="rule",
        render_profile="off",
        preference=strong_groove_preference(),
    )

    assert len(pool) == 16
    assert sum(item.metadata.preference_guided for item in pool) == 8
    assert all(item.intent == requested for item in pool)
    assert all(item.analysis is not None for item in pool)
    guided = [item for item in pool if item.metadata.preference_guided]
    normal = [item for item in pool if not item.metadata.preference_guided]
    assert all(item.metadata.preference_guided_features == ["density"] for item in guided)
    assert all(item.metadata.preference_guidance_strength == pytest.approx(0.35) for item in guided)
    assert all(item.metadata.preference_guidance_strength == 0 for item in normal)


def test_preference_guided_candidate_pool_is_deterministic() -> None:
    kwargs = {
        "bpm": 100,
        "bars": 1,
        "meter": meter(),
        "intent": intent(density=0.1),
        "seed": 1702,
        "performance_mode": "rule",
        "render_profile": "off",
        "preference": strong_groove_preference(),
    }

    left = generate_candidate_pool(**kwargs)
    right = generate_candidate_pool(**kwargs)
    assert [item.model_dump_json() for item in left] == [
        item.model_dump_json() for item in right
    ]


@pytest.mark.parametrize("subdivisions", [2, 3, 4, 6, 8])
def test_generation_supports_exact_binary_and_triplet_grids(subdivisions):
    grid_meter = MeterDefinition(
        numerator=4,
        denominator=4,
        grouping=[2, 2],
        subdivisions_per_quarter=subdivisions,
    )
    pattern = generate_pattern(
        bpm=105,
        bars=2,
        meter=grid_meter,
        intent=intent(density=0.95, variation=0.8),
        seed=31,
    )
    assert all(event.grid_tick % grid_meter.subdivision_tick == 0 for event in pattern.events)
    measured_values = analyze_pattern(pattern).measured_dna.model_dump().values()
    assert all(0 <= value <= 1 for value in measured_values)
    if subdivisions in (3, 6, 8):
        assert any(event.grid_tick % 240 for event in pattern.events)
