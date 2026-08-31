from __future__ import annotations

import math

import numpy as np

from app.config import MAX_MICROTIMING_US, PPQ
from app.engine.pulse import metric_gravity

from .harmony import harmony_at, scale_pitch_classes
from .models import (
    AtomicBassFeatures,
    BassAnalysis,
    BassListenerAnalysis,
    BassPattern,
    DerivedBassDNA,
    HarmonicRole,
    MetricResult,
    RhythmBassInteractionDNA,
    RhythmicRole,
)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _ratio(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _active_occupancy(pattern: BassPattern) -> float:
    end = pattern.bars * pattern.meter.bar_ticks
    intervals = sorted(
        (event.performed_tick, min(end, event.performed_tick + event.duration_tick))
        for event in pattern.events
    )
    active = 0
    cursor_start = cursor_end = 0
    for start, stop in intervals:
        if stop <= start:
            continue
        if start > cursor_end:
            active += cursor_end - cursor_start
            cursor_start, cursor_end = start, stop
        else:
            cursor_end = max(cursor_end, stop)
    active += cursor_end - cursor_start
    return clamp(active / max(1, end))


def _motif_similarity(pattern: BassPattern) -> float:
    signatures: list[set[tuple[int, str]]] = []
    for bar in range(pattern.bars):
        start = bar * pattern.meter.bar_ticks
        signatures.append(
            {
                (
                    (event.grid_tick - start) // pattern.meter.subdivision_tick,
                    event.harmonic_role.value,
                )
                for event in pattern.events
                if start <= event.grid_tick < start + pattern.meter.bar_ticks
            }
        )
    if len(signatures) < 2:
        return 1.0
    similarities = [
        len(left & right) / max(1, len(left | right))
        for left, right in zip(signatures, signatures[1:])
    ]
    return clamp(float(np.mean(similarities)))


def _kick_metrics(pattern: BassPattern) -> tuple[float | None, float | None, float | None, float]:
    if not pattern.groove_context or not pattern.groove_context.kick_events:
        return None, None, None, 0.0
    kicks = [event.performed_tick for event in pattern.groove_context.kick_events]
    bass = [event.performed_tick for event in pattern.events]
    lock = _ratio([any(abs(onset - kick) <= 80 for kick in kicks) for onset in bass])
    complement_candidates = [
        onset for onset in bass if not any(abs(onset - kick) <= PPQ // 4 for kick in kicks)
    ]
    complement = len(complement_candidates) / max(1, len(bass))
    answers = _ratio([any(0 < onset - kick <= PPQ // 2 for kick in kicks) for onset in bass])
    anticipations = _ratio([any(0 < kick - onset <= PPQ // 4 for kick in kicks) for onset in bass])
    return clamp(lock), clamp(complement), clamp(answers), clamp(anticipations)


def measure_atomic_features(pattern: BassPattern) -> AtomicBassFeatures:
    events = pattern.events
    intervals = [abs(right.pitch - left.pitch) for left, right in zip(events, events[1:])]
    total_steps = pattern.bars * pattern.meter.bar_ticks / (PPQ // 4)
    occupancy = _active_occupancy(pattern)
    kick_lock, kick_complement, kick_answer, _ = _kick_metrics(pattern)
    roots = [
        event.harmonic_role in (HarmonicRole.ROOT, HarmonicRole.STRUCTURAL_ROOT) for event in events
    ]
    chord_roles = {
        HarmonicRole.STRUCTURAL_ROOT,
        HarmonicRole.ROOT,
        HarmonicRole.THIRD,
        HarmonicRole.FIFTH,
        HarmonicRole.SEVENTH,
        HarmonicRole.EXTENSION,
        HarmonicRole.TARGET,
    }
    scale_flags = []
    chromatic_flags = []
    for event in events:
        harmony = harmony_at(pattern.harmony, event.grid_tick)
        scale = scale_pitch_classes(harmony.key_context or pattern.key_context)
        scale_flags.append(event.pitch % 12 in scale)
        chromatic_flags.append(
            event.harmonic_role == HarmonicRole.CHROMATIC_APPROACH
            or (event.pitch % 12 not in scale and event.harmonic_role not in chord_roles)
        )
    chromatic_events = [event for event, flag in zip(events, chromatic_flags) if flag]
    ids = {event.event_id for event in events}
    resolved = _ratio(
        [
            bool(event.approach_target_id and event.approach_target_id in ids)
            for event in chromatic_events
        ]
    )
    sync_values = [
        1 - metric_gravity(pattern.meter, event.grid_tick)
        for event in events
        if event.rhythmic_role in (RhythmicRole.ANTICIPATION, RhythmicRole.VIOLATION)
        or metric_gravity(pattern.meter, event.grid_tick) < 0.5
    ]
    motif = _motif_similarity(pattern)
    return AtomicBassFeatures(
        root_ratio=_ratio(roots),
        structural_root_ratio=_ratio(
            [event.harmonic_role == HarmonicRole.STRUCTURAL_ROOT for event in events]
        ),
        chord_tone_ratio=_ratio([event.harmonic_role in chord_roles for event in events]),
        scale_tone_ratio=_ratio(scale_flags),
        chromatic_ratio=_ratio(chromatic_flags),
        resolved_chromatic_ratio=resolved if chromatic_events else 1.0,
        approach_ratio=_ratio(
            [
                event.harmonic_role in (HarmonicRole.APPROACH, HarmonicRole.CHROMATIC_APPROACH)
                for event in events
            ]
        ),
        passing_ratio=_ratio([event.harmonic_role == HarmonicRole.PASSING for event in events]),
        onset_density=clamp(len(events) / max(1, total_steps)),
        active_occupancy=occupancy,
        silence_ratio=1 - occupancy,
        syncopation_index=clamp(float(np.mean(sync_values)) if sync_values else 0),
        anticipation_ratio=_ratio(
            [event.rhythmic_role == RhythmicRole.ANTICIPATION for event in events]
        ),
        mean_interval=float(np.mean(intervals)) if intervals else 0,
        step_ratio=_ratio([interval <= 2 for interval in intervals]),
        leap_ratio=_ratio([interval >= 7 for interval in intervals]),
        octave_ratio=_ratio([interval == 12 for interval in intervals]),
        register_mean=float(np.mean([event.pitch for event in events])) if events else 0,
        register_span=(max(event.pitch for event in events) - min(event.pitch for event in events))
        if events
        else 0,
        register_variance=float(np.var([event.pitch for event in events])) if events else 0,
        duration_variance=float(np.var([event.duration_tick for event in events])) if events else 0,
        velocity_variance=float(np.var([event.velocity for event in events])) if events else 0,
        kick_lock_ratio=kick_lock,
        kick_complement_score=kick_complement,
        kick_answer_score=kick_answer,
        motif_similarity=motif,
        repetition_score=motif,
    )


def derive_dna(atomic: AtomicBassFeatures, pattern: BassPattern) -> DerivedBassDNA:
    harmonic = clamp(
        0.48 * atomic.chord_tone_ratio
        + 0.25 * atomic.scale_tone_ratio
        + 0.17 * atomic.resolved_chromatic_ratio
        + 0.10 * atomic.root_ratio
    )
    motion = clamp(
        atomic.mean_interval / 10 * 0.55
        + (1 - atomic.step_ratio) * 0.25
        + atomic.register_span / 30 * 0.20
    )
    sync_balance = math.exp(-((atomic.syncopation_index - 0.48) ** 2) / 0.15)
    pulse = clamp(
        0.42 * atomic.repetition_score
        + 0.38 * (1 - atomic.syncopation_index * 0.55)
        + 0.20 * atomic.root_ratio
    )
    low_end = clamp(atomic.root_ratio * 0.55 + pulse * 0.45)
    kick_values = [
        value
        for value in (
            atomic.kick_lock_ratio,
            atomic.kick_complement_score,
            atomic.kick_answer_score,
        )
        if value is not None
    ]
    kick_quality = (
        clamp(max(kick_values) * 0.7 + float(np.mean(kick_values)) * 0.3) if kick_values else None
    )
    activity = clamp(atomic.onset_density * 1.7 + atomic.active_occupancy * 0.65)
    motor = clamp(
        0.34 * pulse
        + 0.24 * sync_balance
        + 0.18 * atomic.repetition_score
        + 0.14 * (kick_quality if kick_quality is not None else pulse)
        + 0.10 * math.exp(-((activity - 0.55) ** 2) / 0.18)
    )
    phrase_development = clamp((1 - atomic.motif_similarity) * 0.58 + motion * 0.42)
    tension = clamp(
        0.35 * atomic.chromatic_ratio
        + 0.25 * atomic.syncopation_index
        + 0.20 * atomic.leap_ratio
        + 0.20 * activity
    )
    recovery_events = _ratio(
        [event.rhythmic_role == RhythmicRole.RECOVERY for event in pattern.events]
    )
    resolution = clamp(
        0.42 * atomic.resolved_chromatic_ratio
        + 0.30 * harmonic
        + 0.28 * min(1, recovery_events * 8)
    )
    timing = (
        clamp(
            float(np.mean([abs(event.micro_offset_us) for event in pattern.events]))
            / (MAX_MICROTIMING_US * 0.35)
        )
        if pattern.events
        else 0
    )
    return DerivedBassDNA(
        harmonic_stability=harmonic,
        melodic_motion=motion,
        pulse_support=pulse,
        low_end_anchor=low_end,
        kick_relationship_quality=kick_quality,
        motor_affordance=motor,
        phrase_development=phrase_development,
        motif_identity=atomic.motif_similarity,
        tension=tension,
        resolution_strength=resolution,
        timing_character_strength=timing,
    )


def _metric(value: float | None, applicable: bool = True, confidence: float = 0.78) -> MetricResult:
    return MetricResult(
        value=clamp(value) if value is not None else None,
        confidence=confidence if applicable else 0,
        applicable=applicable,
    )


def _listener(atomic: AtomicBassFeatures, dna: DerivedBassDNA) -> BassListenerAnalysis:
    voice = clamp(
        0.55 * atomic.step_ratio
        + 0.25 * (1 - atomic.leap_ratio)
        + 0.20 * min(1, atomic.register_span / 12)
    )
    rhythmic = clamp(
        0.58 * dna.pulse_support + 0.42 * math.exp(-((atomic.syncopation_index - 0.42) ** 2) / 0.18)
    )
    phrase = clamp(0.55 * dna.motif_identity + 0.45 * (1 - abs(dna.phrase_development - 0.42)))
    boredom = clamp(
        dna.motif_identity * (1 - dna.phrase_development) * (1 - atomic.chromatic_ratio)
    )
    overactivity = clamp(
        max(0, atomic.onset_density - 0.58) * 1.7 + max(0, atomic.active_occupancy - 0.82)
    )
    confusion = clamp(
        (1 - dna.harmonic_stability) * 0.46
        + atomic.leap_ratio * 0.24
        + atomic.chromatic_ratio * (1 - atomic.resolved_chromatic_ratio) * 0.30
    )
    resolvable = clamp(dna.tension * dna.resolution_strength)
    novelty = clamp((1 - dna.motif_identity) * 0.6 + dna.phrase_development * 0.4)
    learning = clamp(dna.motif_identity * dna.phrase_development - confusion * 0.25)
    kick_applicable = dna.kick_relationship_quality is not None
    kick_value = dna.kick_relationship_quality
    predicted = clamp(
        0.20 * rhythmic
        + 0.18 * dna.motor_affordance
        + 0.14 * phrase
        + 0.13 * dna.harmonic_stability
        + 0.10 * resolvable
        + 0.10 * (kick_value if kick_value is not None else dna.pulse_support)
        + 0.08 * learning
        + 0.07 * novelty
        - 0.11 * boredom
        - 0.13 * confusion
        - 0.10 * overactivity
    )
    interest = clamp(
        0.28 * dna.melodic_motion
        + 0.25 * dna.phrase_development
        + 0.22 * novelty
        + 0.15 * dna.tension
        + 0.10 * voice
    )
    return BassListenerAnalysis(
        rhythmic_coherence=_metric(rhythmic),
        harmonic_coherence=_metric(dna.harmonic_stability),
        pitch_motion_quality=_metric(clamp(0.6 * voice + 0.4 * dna.melodic_motion)),
        voice_leading_quality=_metric(voice),
        phrase_coherence=_metric(phrase),
        motif_identity=_metric(dna.motif_identity),
        kick_bass_quality=_metric(kick_value, kick_applicable, 0.72),
        pulse_support=_metric(dna.pulse_support),
        motor_affordance=_metric(dna.motor_affordance),
        resolvable_tension=_metric(resolvable),
        learning_progress=_metric(learning, confidence=0.56),
        boredom=_metric(boredom),
        confusion=_metric(confusion),
        overactivity=_metric(overactivity),
        novelty=_metric(novelty),
        predicted_bass_groove=_metric(predicted, confidence=0.68),
        musical_interest=_metric(interest, confidence=0.70),
    )


def _intent_loss(pattern: BassPattern, atomic: AtomicBassFeatures, dna: DerivedBassDNA) -> float:
    target = pattern.intent.target
    mappings = {
        "root_strength": atomic.root_ratio,
        "chord_tone_strength": atomic.chord_tone_ratio,
        "chromaticism": atomic.chromatic_ratio,
        "approach_activity": atomic.approach_ratio,
        "melodic_motion": dna.melodic_motion,
        "stepwise_motion": atomic.step_ratio,
        "leap_activity": atomic.leap_ratio,
        "register_motion": clamp(atomic.register_span / 30),
        "syncopation": atomic.syncopation_index,
        "kick_lock": atomic.kick_lock_ratio,
        "kick_complement": atomic.kick_complement_score,
        "kick_answer": atomic.kick_answer_score,
        "density": clamp(atomic.onset_density * 1.7),
        "silence": atomic.silence_ratio,
        "duration_contrast": clamp(math.sqrt(atomic.duration_variance) / PPQ),
        "velocity_contrast": clamp(math.sqrt(atomic.velocity_variance) / 30),
        "repetition": atomic.repetition_score,
        "variation": dna.phrase_development,
        "phrase_development": dna.phrase_development,
        "tension": dna.tension,
        "resolution_strength": dna.resolution_strength,
        "human_feel": dna.timing_character_strength,
    }
    skipped = {key for key, value in mappings.items() if value is None}
    distances = []
    for key, measured in mappings.items():
        if key in skipped or measured is None:
            continue
        wanted = getattr(target, key)
        tolerance = pattern.intent.tolerances.per_dimension.get(
            key, pattern.intent.tolerances.default
        )
        distance = abs(wanted - measured)
        distances.append(max(0, distance - tolerance) + min(distance, tolerance) * 0.15)
    return float(np.mean(distances)) if distances else 0


def _interaction(
    pattern: BassPattern, atomic: AtomicBassFeatures, dna: DerivedBassDNA
) -> RhythmBassInteractionDNA | None:
    lock, complement, answer, anticipation = _kick_metrics(pattern)
    if lock is None or complement is None or answer is None:
        return None
    phase = clamp(0.65 * lock + 0.35 * (1 - dna.timing_character_strength * 0.35))
    complexity_balance = clamp(1 - abs(atomic.onset_density - 0.34))
    return RhythmBassInteractionDNA(
        kick_bass_lock=lock,
        kick_bass_complement=complement,
        kick_bass_answer=answer,
        kick_bass_anticipation=anticipation,
        perceived_phase_coherence=phase,
        low_end_complexity_balance=complexity_balance,
        shared_tension=clamp(dna.tension * (0.6 + (1 - lock) * 0.4)),
        shared_recovery=clamp(dna.resolution_strength * (0.6 + lock * 0.4)),
        low_end_space=atomic.silence_ratio,
        pulse_reinforcement=clamp(0.55 * dna.pulse_support + 0.45 * lock),
    )


def analyze_bass_pattern(pattern: BassPattern) -> BassAnalysis:
    atomic = measure_atomic_features(pattern)
    dna = derive_dna(atomic, pattern)
    listener = _listener(atomic, dna)
    loss = _intent_loss(pattern, atomic, dna)
    predicted = listener.predicted_bass_groove.value or 0
    # Intent has the required dominant weight; no atomic feature is directly re-counted here.
    fitness = (
        0.45 * (1 - loss)
        + 0.12 * (listener.rhythmic_coherence.value or 0)
        + 0.12 * (listener.harmonic_coherence.value or 0)
        + 0.10 * (listener.phrase_coherence.value or 0)
        + 0.08 * (listener.voice_leading_quality.value or 0)
        + 0.08
        * (listener.kick_bass_quality.value if listener.kick_bass_quality.applicable else predicted)
        + 0.05 * (listener.novelty.value or 0)
    )
    pattern.interaction_analysis = _interaction(pattern, atomic, dna)
    return BassAnalysis(
        atomic=atomic, dna=dna, listener=listener, intent_loss=loss, fitness=fitness
    )
