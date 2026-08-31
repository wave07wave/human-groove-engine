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
                (e.instrument.value, (e.grid_tick - start) // pattern.meter.subdivision_tick)
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
    step_tick = pattern.meter.subdivision_tick
    for bar in range(pattern.bars):
        bar_start = bar * pattern.meter.bar_ticks
        bar_events = [
            event
            for event in pattern.events
            if bar_start <= event.grid_tick < bar_start + pattern.meter.bar_ticks
        ]
        positions_by_instrument = {
            instrument: {
                event.grid_tick - bar_start
                for event in bar_events
                if event.instrument == instrument
            }
            for instrument in InstrumentID
        }
        for event in bar_events:
            local = event.grid_tick - bar_start
            gravity = metric_gravity(pattern.meter, local)
            next_stronger = 0.0
            for distance in range(1, 5):
                future = local + distance * step_tick
                if future >= pattern.meter.bar_ticks:
                    break
                future_gravity = metric_gravity(pattern.meter, future)
                if (
                    future_gravity > gravity
                    and future not in positions_by_instrument[event.instrument]
                ):
                    next_stronger = max(next_stronger, future_gravity - gravity)
            role_bonus = (
                0.24
                if event.primary_role in (EventRole.VIOLATION, EventRole.ANTICIPATION)
                else 0.0
            )
            score += next_stronger * (0.55 + 0.45 * event.accent) + role_bonus
            possible += 1.0
    # Density and hierarchical displacement are deliberately separate: this value
    # rewards accented weak-to-strong expectation violations, not event count alone.
    return clamp(score / max(1, possible) * 3.2)


def measure_repetition(pattern: GroovePattern) -> float:
    signatures = _bar_signatures(pattern)
    if len(signatures) < 2:
        return 1.0
    similarities = []
    for index, current in enumerate(signatures[1:], start=1):
        similarities.append(
            max(
                len(previous & current) / max(1, len(previous | current))
                for previous in signatures[:index]
            )
        )
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


def measure_microtiming_irregularity(pattern: GroovePattern) -> float:
    """Penalize isolated timing errors while allowing coherent instrument pockets."""
    residual_spreads: list[float] = []
    for instrument in InstrumentID:
        offsets = [e.micro_offset_us for e in pattern.events if e.instrument == instrument]
        if len(offsets) > 1:
            residual_spreads.append(float(np.std(offsets)))
    return clamp(float(np.mean(residual_spreads)) / 9_000) if residual_spreads else 0.0


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


def measure_omission(pattern: GroovePattern) -> float:
    expected = strong_positions(pattern.meter)[1:]
    if not expected:
        return 0.0
    kicks = {event.grid_tick for event in pattern.events if event.instrument == InstrumentID.KICK}
    opportunities = [
        bar * pattern.meter.bar_ticks + local
        for bar in range(pattern.bars)
        for local in expected
    ]
    missing = sum(tick not in kicks for tick in opportunities)
    return clamp(missing / len(opportunities))


def measure_phrase_development(pattern: GroovePattern) -> float:
    if pattern.bars < 2:
        return 0.0
    energies = []
    for bar in range(pattern.bars):
        start = bar * pattern.meter.bar_ticks
        stop = start + pattern.meter.bar_ticks
        events = [event for event in pattern.events if start <= event.grid_tick < stop]
        energies.append(sum((event.velocity / 127) ** 1.25 for event in events))
    edge_energy = (energies[0] + energies[-1]) / 2
    middle = energies[1:-1] or energies
    middle_energy = float(np.mean(middle))
    arch = max(0.0, (middle_energy - edge_energy) / max(1.0, middle_energy + edge_energy))
    contour = float(np.std(energies)) / max(1.0, float(np.mean(energies)))
    return clamp(3.2 * arch + 0.8 * contour)


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
    omission = measure_omission(pattern)
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
        phrase_development=measure_phrase_development(pattern),
    )
