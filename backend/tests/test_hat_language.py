from app.engine.generator import generate_pattern
from app.models.event import EventRole, InstrumentID
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition


def test_hat_language_interlocks_with_phrase_and_drum_voices() -> None:
    intent = GrooveIntent()
    intent.target_dna.density = 0.8
    intent.target_dna.interlock = 0.85
    intent.target_dna.syncopation = 0.75
    intent.target_dna.variation = 0.8
    intent.target_dna.motor_affordance = 0.9
    pattern = generate_pattern(
        bpm=112,
        bars=4,
        meter=MeterDefinition.from_name("4/4"),
        intent=intent,
        seed=712,
        style="Funk",
        performance_mode="rule",
    )
    hats = [event for event in pattern.events if event.instrument == InstrumentID.CLOSED_HAT]
    opens = [event for event in pattern.events if event.instrument == InstrumentID.OPEN_HAT]
    kick_ticks = {
        event.grid_tick for event in pattern.events if event.instrument == InstrumentID.KICK
    }

    assert len(hats) >= pattern.bars * 6
    assert opens
    assert not {event.grid_tick for event in hats} & {event.grid_tick for event in opens}
    assert len({event.primary_role for event in hats}) >= 3
    assert any(
        event.grid_tick - pattern.meter.subdivision_tick in kick_ticks
        for event in hats
        if event.primary_role == EventRole.CONFIRMATION
    )
    per_bar = [
        tuple(
            event.grid_tick % pattern.meter.bar_ticks
            for event in hats
            if event.grid_tick // pattern.meter.bar_ticks == bar
        )
        for bar in range(pattern.bars)
    ]
    assert len(set(per_bar)) >= 2
