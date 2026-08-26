from __future__ import annotations

from copy import deepcopy

from app.config import MAX_MICROTIMING_US, PPQ
from app.random.seeds import HierarchicalRNG

from .analysis import analyze_bass_pattern
from .explain import attach_decision_traces
from .harmony import harmony_at, role_for_pitch, scale_pitch_classes
from .models import (
    AccentType,
    BassPattern,
    BassPreserveOptions,
    ConnectionType,
    HarmonicRole,
    MutationOperation,
    RhythmicRole,
    TechniqueType,
)


def _selected(pattern: BassPattern, bars: set[int]) -> set[int]:
    if not bars:
        return set(range(pattern.bars))
    if any(bar < 0 or bar >= pattern.bars for bar in bars):
        raise ValueError("selected bar outside pattern")
    return bars


def _new_pitch(pattern: BassPattern, index: int, current: int, rng) -> int:
    event = pattern.events[index]
    harmony = harmony_at(pattern.harmony, event.grid_tick)
    if harmony.chord:
        pitch_classes = harmony.chord.pitch_classes
    else:
        pitch_classes = scale_pitch_classes(harmony.key_context or pattern.key_context)
    choices = [
        pitch
        for pitch in range(
            pattern.register_limits.lowest_midi_note,
            pattern.register_limits.highest_midi_note + 1,
        )
        if pitch % 12 in pitch_classes
        and abs(pitch - current) <= pattern.register_limits.max_single_leap
    ]
    if not choices:
        return current
    choices.sort(key=lambda pitch: (abs(pitch - current), pitch))
    window = choices[: min(4, len(choices))]
    return int(window[int(rng.integers(0, len(window)))])


def _repair_onset_collisions(result: BassPattern, original_pattern: BassPattern) -> None:
    pattern_end = result.bars * result.meter.bar_ticks
    original_ticks = {event.event_id: event.grid_tick for event in original_pattern.events}
    moved = [event for event in result.events if event.grid_tick != original_ticks[event.event_id]]
    occupied = {
        event.grid_tick
        for event in result.events
        if event.grid_tick == original_ticks[event.event_id]
    }
    for event in sorted(moved, key=lambda item: (item.grid_tick, item.event_id)):
        preferred = event.grid_tick
        original = original_ticks[event.event_id]
        bar = original // result.meter.bar_ticks
        bar_start = bar * result.meter.bar_ticks
        low = max(bar_start, -event.structural_offset_tick)
        high = min(
            pattern_end - 1,
            bar_start + result.meter.bar_ticks - 1,
            pattern_end - event.duration_tick,
            pattern_end - 1 - event.structural_offset_tick,
        )
        if high < low:
            event.grid_tick = original
            occupied.add(original)
            continue
        if preferred in occupied:
            choices: list[int] = []
            for distance in range(1, high - low + 1):
                choices.extend(
                    tick
                    for tick in (preferred - distance, preferred + distance)
                    if low <= tick <= high and tick not in occupied
                )
                if choices:
                    break
            event.grid_tick = choices[0] if choices else original
        occupied.add(event.grid_tick)


def mutate_bass_pattern(
    pattern: BassPattern,
    bars: set[int],
    operation: MutationOperation,
    preserve: BassPreserveOptions | None = None,
) -> BassPattern:
    preserve = preserve or BassPreserveOptions()
    result = deepcopy(pattern)
    preserve = preserve.model_copy(
        update={
            "keep_rhythm": preserve.keep_rhythm or pattern.intent_locks.keep_rhythm_feel,
            "keep_timing": preserve.keep_timing or pattern.intent_locks.keep_rhythm_feel,
            "keep_kick_relation": (
                preserve.keep_kick_relation or pattern.intent_locks.keep_kick_relationship
            ),
            "keep_register_shape": (
                preserve.keep_register_shape or pattern.intent_locks.keep_register
            ),
        }
    )
    selected = _selected(result, bars)
    revision = result.metadata.revision + 1
    hrng = HierarchicalRNG(result.metadata.master_seed)
    pattern_end = result.bars * result.meter.bar_ticks

    for index, event in enumerate(result.events):
        bar = event.grid_tick // result.meter.bar_ticks
        if bar not in selected:
            continue
        rng = hrng.stream("bass-mutation", revision, operation.value, bar, index)
        provenance = event.provenance.model_copy(
            update={"origin": "regenerated", "mutation_operation": operation.value}
        )
        if operation in (MutationOperation.PITCH_ONLY, MutationOperation.REGENERATE):
            if not preserve.keep_pitch and not event.locks.pitch and event.harmonic_role not in (
                HarmonicRole.APPROACH,
                HarmonicRole.CHROMATIC_APPROACH,
            ):
                event.pitch = _new_pitch(result, index, event.pitch, rng)
                event.harmonic_role = role_for_pitch(
                    event.pitch, harmony_at(result.harmony, event.grid_tick)
                )
                event.provenance = provenance
        if operation in (MutationOperation.TIMING_ONLY, MutationOperation.REGENERATE):
            if (
                not preserve.keep_timing
                and not preserve.keep_kick_relation
                and not event.locks.timing
            ):
                delta = int(rng.normal(0, 800 + 2_800 * result.intent.target.human_feel))
                event.micro_offset_us = max(
                    -MAX_MICROTIMING_US,
                    min(MAX_MICROTIMING_US, event.micro_offset_us + delta),
                )
                event.provenance = provenance
        if operation in (MutationOperation.DURATION_ONLY, MutationOperation.REGENERATE):
            if not preserve.keep_duration and not event.locks.duration:
                factor = float(rng.uniform(0.72, 1.24))
                event.duration_tick = min(
                    pattern_end - event.grid_tick,
                    max(30, round(event.duration_tick * factor)),
                )
                event.provenance = provenance
        if operation in (MutationOperation.ARTICULATION_ONLY, MutationOperation.REGENERATE):
            if not event.locks.articulation:
                event.articulation.connection = (
                    ConnectionType.STACCATO
                    if event.articulation.connection != ConnectionType.STACCATO
                    else ConnectionType.NORMAL
                )
                event.articulation.accent = (
                    AccentType.ACCENT
                    if event.articulation.accent == AccentType.NORMAL
                    else AccentType.NORMAL
                )
                technique_cycle = {
                    TechniqueType.NORMAL: TechniqueType.MUTE,
                    TechniqueType.MUTE: TechniqueType.GHOST,
                    TechniqueType.GHOST: TechniqueType.NORMAL,
                }
                event.articulation.technique = technique_cycle.get(
                    event.articulation.technique, TechniqueType.NORMAL
                )
                event.articulation.legato_overlap_tick = (
                    120 if event.articulation.connection == ConnectionType.LEGATO else 0
                )
                event.provenance = provenance
        if operation in (MutationOperation.RHYTHM_ONLY, MutationOperation.REGENERATE):
            if (
                not preserve.keep_rhythm
                and not preserve.keep_kick_relation
                and not event.locks.timing
                and event.rhythmic_role not in (
                RhythmicRole.ANCHOR,
                RhythmicRole.RECOVERY,
                )
            ):
                step = PPQ // 4
                direction = -1 if rng.random() < 0.5 else 1
                bar_start = bar * result.meter.bar_ticks
                valid_start = max(bar_start, -event.structural_offset_tick)
                bar_end = min(
                    pattern_end - 1,
                    bar_start + result.meter.bar_ticks - 1,
                    pattern_end - event.duration_tick,
                    pattern_end - 1 - event.structural_offset_tick,
                )
                event.grid_tick = max(
                    valid_start, min(bar_end, event.grid_tick + direction * step)
                )
                event.provenance = provenance

        if preserve.keep_motif and event.motif_id:
            original = pattern.events[index]
            event.grid_tick = original.grid_tick
            event.pitch = original.pitch
            event.duration_tick = original.duration_tick
            event.harmonic_role = original.harmonic_role
            event.rhythmic_role = original.rhythmic_role
            event.approach_target_id = original.approach_target_id
            event.provenance = deepcopy(original.provenance)
        elif preserve.keep_register_shape and event.pitch != pattern.events[index].pitch:
            original_pitch = pattern.events[index].pitch
            pitch_class = event.pitch % 12
            same_octave = (original_pitch // 12) * 12 + pitch_class
            candidates = [same_octave - 12, same_octave, same_octave + 12]
            in_range = [
                pitch
                for pitch in candidates
                if result.register_limits.lowest_midi_note
                <= pitch
                <= result.register_limits.highest_midi_note
            ]
            if in_range:
                center = result.register_limits.preferred_center
                same_side = [
                    pitch
                    for pitch in in_range
                    if (pitch - center) * (original_pitch - center) >= 0
                ]
                event.pitch = min(
                    same_side or in_range, key=lambda pitch: abs(pitch - original_pitch)
                )

    result.metadata.revision = revision
    result.pattern_id = f"{pattern.pattern_id}-r{revision}"
    # Only events whose onset was actually mutated may move during collision repair. This preserves
    # locked events, request-level invariants and every non-selected region.
    _repair_onset_collisions(result, pattern)
    attach_decision_traces(result)
    result.analysis = analyze_bass_pattern(result)
    return BassPattern.model_validate(result.model_dump())


def refine_bass_pattern(pattern: BassPattern, strength: float) -> BassPattern:
    source = deepcopy(pattern)
    if not source.analysis:
        source.analysis = analyze_bass_pattern(source)
    analysis = source.analysis
    if analysis.listener.harmonic_coherence.value is not None and (
        analysis.listener.harmonic_coherence.value < 0.72
    ):
        operation = MutationOperation.PITCH_ONLY
    elif analysis.listener.overactivity.value and analysis.listener.overactivity.value > 0.35:
        operation = MutationOperation.DURATION_ONLY
    elif analysis.listener.voice_leading_quality.value is not None and (
        analysis.listener.voice_leading_quality.value < 0.65
    ):
        operation = MutationOperation.PITCH_ONLY
    else:
        operation = (
            MutationOperation.ARTICULATION_ONLY if strength < 0.5 else MutationOperation.REGENERATE
        )
    return mutate_bass_pattern(source, set(), operation)
