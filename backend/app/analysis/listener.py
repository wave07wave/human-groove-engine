from __future__ import annotations

import math

import numpy as np

from app.audio import analyze_reference_render
from app.engine.pulse import metric_gravity
from app.models.analysis import GrooveAnalysis, ListenerAnalysis
from app.models.pattern import GroovePattern

from .embodied import analyze_embodied
from .metrics import clamp, measure_dna, measure_microtiming_irregularity


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
    frequency: dict[tuple[str, int], int] = {}
    for event in pattern.events:
        key = (event.instrument.value, event.grid_tick % pattern.meter.bar_ticks)
        frequency[key] = frequency.get(key, 0) + 1
    bits = []
    for event in pattern.events:
        position = event.grid_tick % pattern.meter.bar_ticks
        learned_probability = frequency[(event.instrument.value, position)] / pattern.bars
        probability = min(
            0.98,
            max(
                0.02,
                0.15 + 0.42 * metric_gravity(pattern.meter, position) + 0.38 * learned_probability,
            ),
        )
        bits.append(min(5.64, -math.log2(probability)) / 5.64)
    return clamp(float(np.mean(bits)))


def analyze_pattern(pattern: GroovePattern, *, include_render: bool = False) -> GrooveAnalysis:
    dna = measure_dna(pattern)
    embodied = analyze_embodied(pattern)
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
    timing_irregularity = measure_microtiming_irregularity(pattern)
    irritation = clamp(
        timing_irregularity * 0.3
        + max(0, dna.density - 0.8) * 0.4
        + max(0, dna.velocity_contrast - 0.75) * 0.18
    )
    learning = clamp(dna.variation * dna.repetition - confusion * 0.3) * 0.5
    balance = clamp(1 - abs(dna.repetition - 0.68) - abs(dna.variation - 0.34) * 0.6)
    legacy_pleasure = clamp(
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
    pleasure = clamp(0.64 * legacy_pleasure + 0.36 * embodied.estimates.pleasure_prior)
    movement = clamp(0.55 * dna.motor_affordance + 0.45 * embodied.estimates.urge_to_move_prior)
    predicted = clamp(0.42 * pleasure + 0.22 * beat + 0.2 * movement + 0.16 * resolvable)
    loss = intent_loss(pattern, dna.model_dump())
    coherence = clamp(0.4 * beat + 0.3 * dna.interlock + 0.3 * dna.recovery_strength)
    fitness = 0.5 * (1 - loss) + 0.3 * predicted + 0.15 * coherence
    listener = ListenerAnalysis(
        predicted_groove=predicted,
        beat_confidence=beat,
        meter_confidence=meter,
        movement_proxy=movement,
        pleasure_proxy=pleasure,
        surprise=surprise,
        resolvable_surprise=resolvable,
        learning_progress=learning,
        boredom=boredom,
        confusion=confusion,
        irritation=irritation,
        confidence=clamp(0.45 + 0.3 * embodied.prediction_error.context_confidence),
    )
    rendered = analyze_reference_render(pattern) if include_render else None
    if rendered is not None:
        embodied.low_end_motion.spectral_flux_50_100hz = rendered.low_frequency_flux
        embodied.low_end_motion.onset_coherence = rendered.kick_bass_onset_coherence
        embodied.low_end_motion.envelope_cycle = rendered.low_end_envelope_cycle
        embodied.low_end_motion.render_applicable = True
        low_render = rendered.low_frequency_flux or 0.0
        embodied.estimates.urge_to_move_prior = clamp(
            embodied.estimates.urge_to_move_prior * 0.9 + low_render * 0.1
        )
    return GrooveAnalysis(
        measured_dna=dna,
        listener=listener,
        intent_loss=loss,
        fitness=fitness,
        rendered_audio=rendered,
        embodied=embodied,
    )
