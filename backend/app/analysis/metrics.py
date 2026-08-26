from __future__ import annotations

import math

import numpy as np

from app.config import MAX_MICROTIMING_US, PPQ
from app.engine.pulse import metric_gravity, strong_positions
from app.models.event import EventRole, InstrumentID
from app.models.groove import GrooveDNA
from app.models.pattern import GroovePattern


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bar_signatures(pattern: GroovePattern) -> list[set[tuple[str, int]]]:
    result: list[set[tuple[str, int]]] = []
    for bar in range(pattern.bars):
        start = bar * pattern.meter.bar_ticks
        result.append(
            {
                (e.instrument.value, (e.grid_tick - start) // (PPQ // 4))
                for e in pattern.events
                if start <= e.grid_tick < start + pattern.meter.bar_ticks
            }
        )
    return result


def measure_density(pattern: GroovePattern) -> float:
    slots = pattern.bars * pattern.meter.bar_ticks / (PPQ // 4)
    active_instruments = len({e.instrument for e in pattern.events}) / len(InstrumentID)
    time_density = len({e.grid_tick for e in pattern.events}) / max(1, slots)
    weighted = sum(e.velocity / 127 for e in pattern.events) / max(1, slots * 2.2)
    return clamp(0.25 * active_instruments + 0.45 * time_density + 0.3 * weighted)


def measure_syncopation(pattern: GroovePattern) -> float:
    if not pattern.events:
        return 0.0
    score = 0.0
    possible = 0.0
    for event in pattern.events:
        gravity = metric_gravity(pattern.meter, event.grid_tick)
        if event.primary_role in (EventRole.VIOLATION, EventRole.ANTICIPATION):
            score += 0.8 + event.accent * 0.5
        elif gravity < 0.5:
            score += (0.5 - gravity) * event.accent
        possible += 1.1
    strong = strong_positions(pattern.meter)
    for bar in range(pattern.bars):
        ticks = {e.grid_tick - bar * pattern.meter.bar_ticks for e in pattern.events}
        score += sum(0.35 for position in strong[1:] if position not in ticks)
        possible += max(0.35, len(strong) * 0.35)
    return clamp(score / max(1, possible) * 2.0)


def measure_repetition(pattern: GroovePattern) -> float:
    signatures = _bar_signatures(pattern)
    if len(signatures) < 2:
        return 1.0
    similarities = []
    for left, right in zip(signatures, signatures[1:]):
        similarities.append(len(left & right) / max(1, len(left | right)))
    return clamp(float(np.mean(similarities)))


def measure_variation(pattern: GroovePattern) -> float:
    signatures = _bar_signatures(pattern)
    if len(signatures) < 2:
        return 0.0
    base = signatures[0]
    changes = [1 - len(base & other) / max(1, len(base | other)) for other in signatures[1:]]
    # A phrase retains motif identity when some, but not all, material changes.
    return clamp(float(np.mean(changes)))


def measure_interlock(pattern: GroovePattern) -> float:
    kicks = {e.grid_tick for e in pattern.events if e.instrument == InstrumentID.KICK}
    bass = {e.grid_tick for e in pattern.events if e.instrument == InstrumentID.BASS}
    percs = {e.grid_tick for e in pattern.events if e.instrument == InstrumentID.PERCUSSION}
    snares = {e.grid_tick for e in pattern.events if e.instrument == InstrumentID.SNARE}
    lock = len(kicks & bass) / max(1, len(kicks | bass))
    complement = len(percs - kicks - snares) / max(1, len(percs))
    return clamp(0.65 * lock + 0.35 * complement)


def measure_swing(pattern: GroovePattern) -> float:
    offsets = [abs(e.structural_offset_tick) for e in pattern.events]
    return clamp(float(np.mean(offsets)) / (PPQ // 4 * 0.25)) if offsets else 0.0


def measure_microtiming(pattern: GroovePattern) -> float:
    offsets = [abs(e.micro_offset_us) for e in pattern.events]
    return clamp(float(np.mean(offsets)) / (MAX_MICROTIMING_US * 0.4)) if offsets else 0.0


def measure_velocity_contrast(pattern: GroovePattern) -> float:
    values = [e.velocity for e in pattern.events]
    return clamp(float(np.std(values)) / 35) if values else 0.0


def measure_duration_contrast(pattern: GroovePattern) -> float:
    values = [e.duration_tick for e in pattern.events]
    return clamp(float(np.std(values)) / PPQ) if values else 0.0


def measure_low_end_anchor(pattern: GroovePattern) -> float:
    events = [e for e in pattern.events if e.instrument in (InstrumentID.KICK, InstrumentID.BASS)]
    if not events:
        return 0.0
    aligned = np.mean(
        [metric_gravity(pattern.meter, e.grid_tick) * e.velocity / 127 for e in events]
    )
    roles = np.mean(
        [
            e.primary_role in (EventRole.ANCHOR, EventRole.CONFIRMATION, EventRole.RECOVERY)
            for e in events
        ]
    )
    return clamp(0.65 * aligned + 0.35 * roles)


def measure_metric_ambiguity(pattern: GroovePattern) -> float:
    if not pattern.events:
        return 1.0
    weighted = sum(metric_gravity(pattern.meter, e.grid_tick) * e.accent for e in pattern.events)
    total = sum(e.accent for e in pattern.events)
    return clamp(1 - weighted / max(1e-9, total))


def measure_ghost_density(pattern: GroovePattern) -> float:
    return clamp(
        sum(e.primary_role == EventRole.GHOST for e in pattern.events)
        / max(1, len(pattern.events))
        * 8
    )


def measure_dna(pattern: GroovePattern) -> GrooveDNA:
    repetition = measure_repetition(pattern)
    variation = measure_variation(pattern)
    density = measure_density(pattern)
    syncopation = measure_syncopation(pattern)
    low_end = measure_low_end_anchor(pattern)
    ambiguity = measure_metric_ambiguity(pattern)
    recovery_events = [e for e in pattern.events if e.primary_role == EventRole.RECOVERY]
    recovery = clamp(len(recovery_events) / max(1, pattern.bars) * 2 + low_end * 0.45)
    beat_salience = clamp(0.55 * low_end + 0.45 * (1 - ambiguity))
    pulse = clamp(0.45 * beat_salience + 0.35 * repetition + 0.2 * (1 - ambiguity))
    surprise = clamp(0.55 * syncopation + 0.3 * ambiguity + 0.15 * variation)
    difficulty = clamp(0.3 * syncopation + 0.25 * density + 0.25 * ambiguity + 0.2 * variation)
    motor = math.exp(-((difficulty - 0.48) ** 2) / 0.12)
    anticipation = sum(e.primary_role == EventRole.ANTICIPATION for e in pattern.events) / max(
        1, len(pattern.events)
    )
    omission = sum(e.primary_role == EventRole.OMISSION_PROXY for e in pattern.events) / max(
        1, pattern.bars
    )
    return GrooveDNA(
        pulse_stability=pulse,
        beat_salience=beat_salience,
        syncopation=syncopation,
        anticipation=clamp(anticipation * 8),
        omission=clamp(omission),
        density=density,
        repetition=repetition,
        variation=variation,
        interlock=measure_interlock(pattern),
        swing=measure_swing(pattern),
        microtiming=measure_microtiming(pattern),
        velocity_contrast=measure_velocity_contrast(pattern),
        duration_contrast=measure_duration_contrast(pattern),
        low_end_anchor=low_end,
        metric_ambiguity=ambiguity,
        ghost_density=measure_ghost_density(pattern),
        surprise=surprise,
        recovery_strength=recovery,
        motor_affordance=clamp(motor),
        hypnotic=clamp(repetition * (1 - surprise * 0.5)),
        phrase_development=clamp(0.55 * variation + 0.45 * density),
    )
