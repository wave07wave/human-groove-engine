from __future__ import annotations

from dataclasses import dataclass

from app.models.meter import MeterDefinition

from .pulse import metric_gravity


@dataclass(frozen=True)
class PhraseRhythmFigure:
    """A meter-aware call, answer and turnaround shared by one motif bar."""

    call_tick: int
    answer_tick: int
    turnaround_tick: int


_MOTIF_OFFSETS = {"A": 0, "A'": 1, "A''": 2, "B": 2, "C": 3}


def phrase_rhythm_figure(meter: MeterDefinition, motif: str) -> PhraseRhythmFigure:
    """Choose stable weak-grid landmarks without assuming 4/4 or sixteenth notes."""
    step = meter.subdivision_tick
    steps = meter.bar_ticks // step
    weak_slots = [
        slot
        for slot in range(1, max(1, steps - 1))
        if metric_gravity(meter, slot * step) < 0.5
    ]
    if not weak_slots:
        weak_slots = list(range(1, max(2, steps - 1))) or [0]
    offset = _MOTIF_OFFSETS.get(motif, 0) % len(weak_slots)
    call_slot = weak_slots[offset]
    answer_slot = weak_slots[(offset + max(1, len(weak_slots) // 3)) % len(weak_slots)]
    turnaround_slot = weak_slots[(offset - 1) % len(weak_slots)]
    return PhraseRhythmFigure(
        call_tick=call_slot * step,
        answer_tick=answer_slot * step,
        turnaround_tick=turnaround_slot * step,
    )
