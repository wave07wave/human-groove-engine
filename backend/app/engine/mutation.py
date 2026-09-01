from copy import deepcopy

from app.models.event import InstrumentID
from app.models.pattern import GroovePattern

from .generator import generate_pattern

HI_HAT_INSTRUMENTS = {InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT}


def _merge_phrase_metadata(
    original: list[str], fresh: list[str], bars: set[int], total_bars: int
) -> list[str]:
    """Keep phrase explanations truthful after a partial bar replacement."""
    merged = (original + [""] * total_bars)[:total_bars]
    for bar in bars:
        if 0 <= bar < len(fresh):
            merged[bar] = fresh[bar]
    return merged


def _normalise_hi_hat_chokes(events: list) -> list:
    """Keep one hi-hat articulation per tick after partial edits or regeneration."""
    by_tick: dict[int, list] = {}
    for event in events:
        if event.instrument in HI_HAT_INSTRUMENTS:
            by_tick.setdefault(event.grid_tick, []).append(event)
    remove_ids: set[str] = set()
    for same_tick in by_tick.values():
        instruments = {event.instrument for event in same_tick}
        if instruments != HI_HAT_INSTRUMENTS:
            continue
        protected = [event for event in same_tick if event.locked or event.origin == "user_edited"]
        if len(protected) > 1:
            # Preserve an existing user-authored collision rather than silently
            # deleting a locked or manually edited event during regeneration.
            continue
        if len(protected) == 1:
            keep = protected[0]
        else:
            # An open hit intentionally replaces a closed hit in this engine.
            keep = next(event for event in same_tick if event.instrument == InstrumentID.OPEN_HAT)
        remove_ids.update(event.event_id for event in same_tick if event.event_id != keep.event_id)
    return [event for event in events if event.event_id not in remove_ids]


def regenerate_selected(
    pattern: GroovePattern,
    instruments: set[InstrumentID],
    bars: set[int],
    operation: str = "regenerate",
) -> GroovePattern:
    instruments = set(instruments)
    bars = set(bars)
    if not instruments:
        instruments = set(InstrumentID) - pattern.instrument_locks
    if not bars:
        bars = set(range(pattern.bars)) - pattern.bar_locks
    instruments -= pattern.instrument_locks
    bars -= pattern.bar_locks
    # Closed and open hats form one choke family.  Regenerating just one lane
    # must not leave a stale articulation at the same tick in the other lane.
    if instruments & HI_HAT_INSTRUMENTS:
        instruments |= HI_HAT_INSTRUMENTS - pattern.instrument_locks
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
        detroit_soul=pattern.metadata.detroit_soul,
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
        _normalise_hi_hat_chokes(kept + replacements),
        key=lambda e: (e.grid_tick, e.instrument.value, e.event_id),
    )
    result.metadata.master_seed += 1
    result.metadata.hat_variant_ids = _merge_phrase_metadata(
        pattern.metadata.hat_variant_ids,
        fresh.metadata.hat_variant_ids,
        bars,
        pattern.bars,
    )
    result.metadata.drum_variant_ids = _merge_phrase_metadata(
        pattern.metadata.drum_variant_ids,
        fresh.metadata.drum_variant_ids,
        bars,
        pattern.bars,
    )
    result.metadata.phrase_arrangement_ids = _merge_phrase_metadata(
        pattern.metadata.phrase_arrangement_ids,
        fresh.metadata.phrase_arrangement_ids,
        bars,
        pattern.bars,
    )
    if instruments and bars:
        result.metadata.embodied_operator_arm = (
            fresh.metadata.embodied_operator_arm
            if instruments == set(InstrumentID) and bars == set(range(pattern.bars))
            else (
                "mixed:"
                f"{pattern.metadata.embodied_operator_arm}+"
                f"{fresh.metadata.embodied_operator_arm}"
            )
        )
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
