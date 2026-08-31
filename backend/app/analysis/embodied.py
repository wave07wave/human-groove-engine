"""Explainable embodied-groove features.

These are candidate-ranking and research features, not physiological measurements.
They deliberately stay outside GrooveDNA until human evaluation supports promotion.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from app.config import MAX_MICROTIMING_US, PPQ
from app.engine.pulse import metric_gravity, strong_positions
from app.models.analysis import (
    EmbodiedEstimates,
    EmbodiedGrooveFeatures,
    LowEndMotionAnalysis,
    MetricLevelAnalysis,
    MotorScaffoldAnalysis,
    PhraseRenewalAnalysis,
    PredictionErrorAnalysis,
    TimingCoherenceAnalysis,
)
from app.models.event import EventRole, InstrumentID
from app.models.pattern import GroovePattern


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _weight(event) -> float:
    base = event.velocity / 127 * (0.45 + 0.55 * event.accent)
    if event.instrument in (InstrumentID.KICK, InstrumentID.BASS):
        base *= 1.2
    if event.primary_role in (EventRole.ANCHOR, EventRole.RECOVERY):
        base *= 1.25
    if event.primary_role == EventRole.GHOST:
        base *= 0.35
    return base


def _level(pattern: GroovePattern, period: int) -> MetricLevelAnalysis:
    events = pattern.events
    if not events or period <= 0:
        return MetricLevelAnalysis(clarity=0, phase_stability=0, activity=0)
    weighted = [(event, _weight(event)) for event in events]
    # A repeatable phase within each period creates a usable movement foothold.
    phases: dict[int, float] = defaultdict(float)
    for event, weight in weighted:
        phases[event.performed_tick % period] += weight
    values = np.array(list(phases.values()), dtype=float)
    total = float(values.sum())
    if total <= 0:
        concentration = 0.0
    elif len(values) == 1:
        concentration = 1.0
    else:
        probabilities = values / total
        entropy = -float(np.sum(probabilities * np.log(probabilities + 1e-12)))
        concentration = _clamp(1 - entropy / math.log(len(values)))
    cycle_count = max(1, math.ceil(pattern.bars * pattern.meter.bar_ticks / period))
    occupied = {event.performed_tick // period for event, weight in weighted if weight > 0.08}
    activity = _clamp(len(occupied) / cycle_count)
    # A phase becomes more reliable when it occurs in many bars, not just one fill.
    per_bar: list[set[int]] = []
    for bar in range(pattern.bars):
        start, end = bar * pattern.meter.bar_ticks, (bar + 1) * pattern.meter.bar_ticks
        per_bar.append(
            {event.performed_tick % period for event in events if start <= event.grid_tick < end}
        )
    common = set.intersection(*per_bar) if per_bar and all(per_bar) else set()
    stability = _clamp(len(common) / max(1, len(phases)))
    return MetricLevelAnalysis(
        clarity=_clamp(0.5 * concentration + 0.3 * activity + 0.2 * stability),
        phase_stability=stability,
        activity=activity,
    )


def motor_scaffold(pattern: GroovePattern) -> MotorScaffoldAnalysis:
    meter = pattern.meter
    return MotorScaffoldAnalysis(
        subdivision=_level(pattern, meter.subdivision_tick),
        tactus=_level(pattern, PPQ),
        half_time=_level(pattern, 2 * PPQ),
        bar_cycle=_level(pattern, meter.bar_ticks),
    )


def prediction_error(pattern: GroovePattern) -> PredictionErrorAnalysis:
    if not pattern.events:
        return PredictionErrorAnalysis(
            event_surprise=1,
            omission_surprise=1,
            concentration=1,
            recoverable_ratio=0,
            context_confidence=0,
        )
    meter = pattern.meter
    occurrence: dict[tuple[str, int], int] = defaultdict(int)
    for event in pattern.events:
        occurrence[(event.instrument.value, event.grid_tick % meter.bar_ticks)] += 1
    surprises: list[float] = []
    violation_ticks: list[int] = []
    for event in pattern.events:
        local = event.grid_tick % meter.bar_ticks
        repeated = occurrence[(event.instrument.value, local)] / max(1, pattern.bars)
        probability = _clamp(0.08 + 0.48 * metric_gravity(meter, local) + 0.38 * repeated)
        surprise = min(1.0, -math.log2(max(0.02, probability)) / 5.64)
        surprises.append(surprise)
        if event.primary_role in (EventRole.VIOLATION, EventRole.ANTICIPATION):
            violation_ticks.append(event.grid_tick)
    omissions: list[float] = []
    strong = strong_positions(meter)
    for bar in range(pattern.bars):
        for local in strong:
            expected = _clamp(0.42 + 0.5 * metric_gravity(meter, local))
            has_low_anchor = any(
                event.grid_tick == bar * meter.bar_ticks + local
                and event.instrument in (InstrumentID.KICK, InstrumentID.BASS)
                for event in pattern.events
            )
            if not has_low_anchor:
                omissions.append(expected)
    recovered = 0
    for tick in violation_ticks:
        recovered += any(
            tick < event.grid_tick <= tick + 2 * PPQ
            and event.instrument == InstrumentID.KICK
            and event.primary_role in (EventRole.ANCHOR, EventRole.RECOVERY, EventRole.CONFIRMATION)
            for event in pattern.events
        )
    bins: dict[int, int] = defaultdict(int)
    for tick in violation_ticks:
        bins[tick // PPQ] += 1
    concentration = _clamp(max(bins.values(), default=0) / max(1, len(violation_ticks)))
    embodied = pattern.intent.embodied
    context_confidence = _clamp(
        0.25 + 0.35 * embodied.meter_familiarity + 0.35 * embodied.style_familiarity
    )
    return PredictionErrorAnalysis(
        event_surprise=_clamp(float(np.mean(surprises))),
        omission_surprise=_clamp(float(np.mean(omissions))) if omissions else 0,
        concentration=concentration,
        recoverable_ratio=recovered / len(violation_ticks) if violation_ticks else 1.0,
        context_confidence=context_confidence,
    )


def timing_coherence(pattern: GroovePattern) -> TimingCoherenceAnalysis:
    by_lane: dict[str, list[float]] = defaultdict(list)
    by_bar: dict[int, list[float]] = defaultdict(list)
    for event in pattern.events:
        value = event.micro_offset_us / 1000
        by_lane[event.instrument.value].append(value)
        by_bar[event.grid_tick // pattern.meter.bar_ticks].append(value)
    lane_offsets = {lane: round(float(np.mean(values)), 3) for lane, values in by_lane.items()}
    dispersions = [
        float(np.std(values)) / (MAX_MICROTIMING_US / 1000)
        for values in by_lane.values()
        if len(values) > 1
    ]
    within = _clamp(float(np.mean(dispersions))) if dispersions else 0.0
    bar_means = [float(np.mean(values)) for values in by_bar.values() if values]
    shared = (
        _clamp(float(np.std(bar_means)) / (MAX_MICROTIMING_US / 1000))
        if len(bar_means) > 1
        else 0.0
    )
    residuals: list[float] = []
    for bar, values in by_bar.items():
        mean = float(np.mean(values))
        residuals.extend(abs(value - mean) for value in values)
    jitter = _clamp(float(np.mean(residuals)) / (MAX_MICROTIMING_US / 1000)) if residuals else 0.0
    pairs = (
        (InstrumentID.KICK.value, InstrumentID.BASS.value),
        (InstrumentID.KICK.value, InstrumentID.SNARE.value),
        (InstrumentID.SNARE.value, InstrumentID.CLOSED_HAT.value),
    )
    pair_values = []
    for left, right in pairs:
        if left in lane_offsets and right in lane_offsets:
            pair_values.append(1 - min(1.0, abs(lane_offsets[left] - lane_offsets[right]) / 18))
    pairwise = float(np.mean(pair_values)) if pair_values else 0.5
    coherence = _clamp(0.45 * (1 - jitter) + 0.25 * (1 - within) + 0.2 * pairwise + 0.1 * shared)
    return TimingCoherenceAnalysis(
        lane_offsets_ms=lane_offsets,
        within_lane_dispersion=within,
        pairwise_phase_coherence=pairwise,
        shared_drift=shared,
        independent_jitter=jitter,
        coherence=coherence,
    )


def phrase_renewal(pattern: GroovePattern) -> PhraseRenewalAnalysis:
    bars: list[set[tuple[str, int, str]]] = []
    density: list[int] = []
    layers: list[set[str]] = []
    for bar in range(pattern.bars):
        events = [
            event for event in pattern.events if event.grid_tick // pattern.meter.bar_ticks == bar
        ]
        bars.append(
            {
                (
                    event.instrument.value,
                    event.grid_tick % pattern.meter.bar_ticks,
                    event.primary_role.value,
                )
                for event in events
            }
        )
        density.append(len(events))
        layers.append({event.instrument.value for event in events})
    similarity = []
    for previous, current in zip(bars, bars[1:]):
        similarity.append(len(previous & current) / max(1, len(previous | current)))
    layer_lifts = [
        max(0, len(current) - len(previous)) / len(InstrumentID)
        for previous, current in zip(layers, layers[1:])
    ]
    challenges = [
        event
        for event in pattern.events
        if event.primary_role in (EventRole.VIOLATION, EventRole.ANTICIPATION, EventRole.TRANSITION)
    ]
    recovery_events = [
        event for event in pattern.events if event.primary_role == EventRole.RECOVERY
    ]
    last_density = density[-1] if density else 0
    reentry = _clamp(
        (
            len(recovery_events)
            + sum(
                event.instrument == InstrumentID.KICK
                for event in pattern.events
                if event.grid_tick // pattern.meter.bar_ticks == pattern.bars - 1
            )
        )
        / max(1, last_density)
    )
    return PhraseRenewalAnalysis(
        motif_memory=_clamp(float(np.mean(similarity))) if similarity else 1.0,
        layer_entry_lift=_clamp(float(np.mean(layer_lifts))) if layer_lifts else 0.0,
        challenge_strength=_clamp(len(challenges) / max(1, len(pattern.events) * 0.22)),
        reentry_strength=reentry,
    )


def analyze_embodied(pattern: GroovePattern) -> EmbodiedGrooveFeatures:
    scaffold = motor_scaffold(pattern)
    prediction = prediction_error(pattern)
    timing = timing_coherence(pattern)
    renewal = phrase_renewal(pattern)
    kick_ticks = {
        event.grid_tick for event in pattern.events if event.instrument == InstrumentID.KICK
    }
    bass_ticks = {
        event.grid_tick for event in pattern.events if event.instrument == InstrumentID.BASS
    }
    coupling = len(kick_ticks & bass_ticks) / max(1, len(kick_ticks | bass_ticks))
    low_end = LowEndMotionAnalysis(symbolic_coupling=_clamp(coupling))
    support = max(scaffold.tactus.clarity, scaffold.half_time.clarity)
    challenge_fit = 1 - abs(prediction.event_surprise - pattern.intent.embodied.challenge)
    urge = _clamp(
        0.3 * support
        + 0.18 * scaffold.bar_cycle.clarity
        + 0.16 * challenge_fit
        + 0.14 * prediction.recoverable_ratio
        + 0.12 * timing.coherence
        + 0.1 * low_end.symbolic_coupling
    )
    pleasure = _clamp(
        0.27 * urge
        + 0.2 * renewal.motif_memory
        + 0.17 * renewal.reentry_strength
        + 0.16 * timing.coherence
        + 0.12 * (1 - prediction.concentration)
        + 0.08 * prediction.context_confidence
    )
    uncertainty = _clamp(
        1
        - prediction.context_confidence * (0.45 + 0.55 * pattern.intent.embodied.meter_familiarity)
    )
    return EmbodiedGrooveFeatures(
        motor_scaffold=scaffold,
        prediction_error=prediction,
        timing_coherence=timing,
        low_end_motion=low_end,
        phrase_renewal=renewal,
        estimates=EmbodiedEstimates(
            urge_to_move_prior=urge, pleasure_prior=pleasure, uncertainty=uncertainty
        ),
    )
