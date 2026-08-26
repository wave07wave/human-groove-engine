from conftest import intent, meter

from app.analysis.listener import analyze_pattern
from app.engine.generator import generate_pattern
from app.engine.mutation import regenerate_selected
from app.engine.optimizer import generate_candidates, pattern_distance
from app.models.event import InstrumentID


def make(seed=42, groove_intent=None, meter_name="4/4", bars=4):
    return generate_pattern(
        bpm=105,
        bars=bars,
        meter=meter(meter_name),
        intent=groove_intent or intent(),
        seed=seed,
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
