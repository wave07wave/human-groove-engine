from __future__ import annotations

from app.engine.pulse import metric_gravity, virtual_beat_map
from app.models.event import InstrumentID
from app.models.pattern import GroovePattern

from .models import GrooveContext, KickEvent, TempoMap, TempoSegment


def groove_context_from_pattern(pattern: GroovePattern) -> GrooveContext:
    """Adapt a public Groove pattern to the stable Bass DTO boundary."""
    step = pattern.meter.subdivision_tick
    end = pattern.bars * pattern.meter.bar_ticks
    tension = [min(1.0, 0.22 + 0.58 * ((bar % 4) / 3)) for bar in range(pattern.bars)]
    return GrooveContext(
        tempo_map=TempoMap(segments=[TempoSegment(start_tick=0, bpm=pattern.bpm)]),
        meter=pattern.meter,
        phrase_boundaries=[tick for tick in range(0, end + 1, pattern.meter.bar_ticks * 4)],
        beat_map=virtual_beat_map(
            pattern.meter, pattern.bars, pattern.intent.target_dna.pulse_stability
        ),
        metric_gravity=[metric_gravity(pattern.meter, tick) for tick in range(0, end, step)],
        tension_curve=tension,
        kick_events=[
            KickEvent(
                grid_tick=event.grid_tick,
                structural_offset_tick=event.structural_offset_tick,
                micro_offset_us=event.micro_offset_us,
                velocity=event.velocity,
            )
            for event in pattern.events
            if event.instrument == InstrumentID.KICK
        ],
        groove_dna=pattern.intent.target_dna.model_dump(),
    )
