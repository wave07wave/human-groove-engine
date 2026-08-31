from copy import deepcopy

from app.models.event import InstrumentID
from app.models.pattern import GroovePattern

from .generator import generate_pattern


def regenerate_selected(
    pattern: GroovePattern,
    instruments: set[InstrumentID],
    bars: set[int],
    operation: str = "regenerate",
) -> GroovePattern:
    if not instruments:
        instruments = set(InstrumentID) - pattern.instrument_locks
    if not bars:
        bars = set(range(pattern.bars)) - pattern.bar_locks
    instruments -= pattern.instrument_locks
    bars -= pattern.bar_locks
    fresh = generate_pattern(
        bpm=pattern.bpm,
        bars=pattern.bars,
        meter=pattern.meter,
        intent=pattern.intent,
        seed=pattern.metadata.master_seed + 1,
        candidate=0,
        name=pattern.name,
        style=pattern.metadata.style,
        performance_mode=(
            "rule" if pattern.metadata.performance_model == "rule-pocket-v1" else "auto"
        ),
        render_profile=pattern.metadata.render_profile,
    )
    result = deepcopy(pattern)
    kept = [
        e
        for e in pattern.events
        if e.locked
        or e.origin == "user_edited"
        or e.instrument not in instruments
        or e.grid_tick // pattern.meter.bar_ticks not in bars
    ]
    replacements = [
        e.model_copy(update={"origin": "regenerated"})
        for e in fresh.events
        if e.instrument in instruments and e.grid_tick // pattern.meter.bar_ticks in bars
    ]
    result.events = sorted(
        kept + replacements, key=lambda e: (e.grid_tick, e.instrument.value, e.event_id)
    )
    result.metadata.master_seed += 1
    if (
        fresh.metadata.performance_model != pattern.metadata.performance_model
        and not pattern.metadata.performance_model.startswith("mixed:")
    ):
        result.metadata.performance_model = (
            f"mixed:{pattern.metadata.performance_model}+{fresh.metadata.performance_model}"
        )
        result.metadata.performance_model_version = fresh.metadata.performance_model_version
    result.pattern_id = f"{pattern.pattern_id}-m{result.metadata.master_seed}"
    result.analysis = None
    return result
