from __future__ import annotations

import math

import numpy as np

from app.engine.pulse import metric_gravity
from app.models.analysis import GrooveAnalysis, ListenerAnalysis
from app.models.pattern import GroovePattern

from .metrics import clamp, measure_dna


def intent_loss(pattern: GroovePattern, measured: dict[str, float]) -> float:
    target = pattern.intent.target_dna.model_dump()
    tolerance = pattern.intent.tolerance
    total = 0.0
    weights = 0.0
    for key, wanted in target.items():
        weight = pattern.intent.priorities.weights.get(key, 0.35)
        distance = abs(wanted - measured[key])
        allowed = tolerance.per_dimension.get(key, tolerance.default)
        penalty = max(0.0, distance - allowed) + min(distance, allowed) * 0.15
        total += weight * penalty
        weights += weight
    return total / max(1e-9, weights)


def _prediction_surprise(pattern: GroovePattern) -> float:
    if not pattern.events:
        return 1.0
    bits = []
    previous = set()
    for event in pattern.events:
        position = event.grid_tick % pattern.meter.bar_ticks
        evidence = 0.35 if (event.instrument.value, position) in previous else 0
        probability = min(
            0.98, max(0.02, 0.3 * metric_gravity(pattern.meter, position) + evidence + 0.15)
        )
        bits.append(min(5.64, -math.log2(probability)) / 5.64)
        previous.add((event.instrument.value, position))
    return clamp(float(np.mean(bits)))


def analyze_pattern(pattern: GroovePattern) -> GrooveAnalysis:
    dna = measure_dna(pattern)
    surprise = _prediction_surprise(pattern)
    beat = clamp(0.45 * dna.pulse_stability + 0.35 * dna.low_end_anchor + 0.2 * dna.repetition)
    meter = clamp(beat * (1 - dna.metric_ambiguity * 0.55))
    resolvable = clamp(surprise * dna.recovery_strength * beat)
    boredom = clamp(dna.repetition * (1 - dna.variation) * (1 - surprise))
    confusion = clamp(
        (1 - beat) * 0.5
        + dna.metric_ambiguity * 0.3
        + dna.syncopation * (1 - dna.recovery_strength) * 0.2
    )
    irritation = clamp(
        dna.microtiming * 0.25 + max(0, dna.density - 0.8) * 0.4 + dna.velocity_contrast * 0.12
    )
    learning = clamp(dna.variation * dna.repetition - confusion * 0.3) * 0.5
    balance = clamp(1 - abs(dna.repetition - 0.68) - abs(dna.variation - 0.34) * 0.6)
    pleasure = clamp(
        0.24 * resolvable
        + 0.24 * dna.motor_affordance
        + 0.22 * beat
        + 0.12 * dna.interlock
        + 0.1 * balance
        + 0.08 * max(0, learning)
        - 0.16 * boredom
        - 0.2 * confusion
        - 0.12 * irritation
    )
    predicted = clamp(
        0.48 * pleasure + 0.22 * beat + 0.16 * dna.motor_affordance + 0.14 * resolvable
    )
    loss = intent_loss(pattern, dna.model_dump())
    coherence = clamp(0.4 * beat + 0.3 * dna.interlock + 0.3 * dna.recovery_strength)
    fitness = 0.5 * (1 - loss) + 0.3 * predicted + 0.15 * coherence
    listener = ListenerAnalysis(
        predicted_groove=predicted,
        beat_confidence=beat,
        meter_confidence=meter,
        movement_proxy=dna.motor_affordance,
        pleasure_proxy=pleasure,
        surprise=surprise,
        resolvable_surprise=resolvable,
        learning_progress=learning,
        boredom=boredom,
        confusion=confusion,
        irritation=irritation,
        confidence=0.72,
    )
    return GrooveAnalysis(measured_dna=dna, listener=listener, intent_loss=loss, fitness=fitness)
