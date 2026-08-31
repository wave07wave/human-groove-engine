from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.config import MAX_MICROTIMING_US, PPQ
from app.engine.pulse import metric_gravity, strong_positions
from app.preference_guidance import PreferenceGuidance, guided_feature_values
from app.random.seeds import HierarchicalRNG

from .analysis import analyze_bass_pattern
from .explain import attach_decision_traces
from .harmony import (
    build_harmony_timeline,
    harmony_at,
    role_for_pitch,
    scale_pitch_classes,
)
from .intent import resolve_intent
from .models import (
    AccentType,
    BassArticulation,
    BassEvent,
    BassGenerateRequest,
    BassIntent,
    BassPattern,
    BassPatternMetadata,
    BassPreferenceSummary,
    BassStructuralEvent,
    BassVoicePolicy,
    ConnectionType,
    EventProvenance,
    HarmonicRole,
    HarmonyTimeline,
    InputMode,
    RegisterLimits,
    RhythmicRole,
    StructuralRole,
    TechniqueType,
    TempoMap,
    TempoSegment,
)
from .preference import blended_candidate_score

BASS_PREFERENCE_TARGETS = {
    "syncopation": "syncopation",
    "density": "density",
    "silence": "silence",
    "root_usage": "root_strength",
    "chromatic_tolerance": "chromaticism",
    "pitch_motion": "melodic_motion",
    "timing": "human_feel",
    "duration": "duration_contrast",
}


@dataclass
class SkeletonEvent:
    event_id: str
    tick: int
    bar: int
    role: RhythmicRole
    weight: float
    phrase_id: str
    motif_id: str
    kick_relation: str
    pitch: int = 36
    harmonic_role: HarmonicRole = HarmonicRole.ROOT
    approach_target_id: str | None = None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _gravity(request: BassGenerateRequest, tick: int) -> float:
    context = request.groove_context
    if context and context.metric_gravity:
        step = request.meter.subdivision_tick
        slot = tick // step
        if tick % step == 0 and slot < len(context.metric_gravity):
            return _clamp(context.metric_gravity[slot])
    return metric_gravity(request.meter, tick)


def _kick_ticks(request: BassGenerateRequest) -> list[int]:
    if not request.groove_context:
        return []
    return sorted(event.performed_tick for event in request.groove_context.kick_events)


def _near_kick(tick: int, kicks: list[int], window: int = 80) -> bool:
    return any(abs(tick - kick) <= window for kick in kicks)


def _kick_relation(tick: int, kicks: list[int], step_tick: int) -> str:
    if not kicks:
        return "independent"
    if _near_kick(tick, kicks):
        return "lock"
    if any(0 < tick - kick <= step_tick * 2 for kick in kicks):
        return "answer"
    if any(0 < kick - tick <= step_tick for kick in kicks):
        return "anticipate"
    return "complement"


def _role_for_position(
    *,
    tick: int,
    local_tick: int,
    bar: int,
    bars: int,
    gravity: float,
    relation: str,
    strong: set[int],
) -> RhythmicRole:
    if bar == bars - 1 and local_tick in strong:
        return RhythmicRole.RECOVERY
    if local_tick == 0:
        return RhythmicRole.ANCHOR
    if relation == "anticipate":
        return RhythmicRole.ANTICIPATION
    if gravity < 0.4:
        return RhythmicRole.VIOLATION
    return RhythmicRole.CONFIRMATION


def _rhythm_skeleton(
    request: BassGenerateRequest,
    intent: BassIntent,
    hrng: HierarchicalRNG,
    candidate: int,
) -> list[SkeletonEvent]:
    strong = set(strong_positions(request.meter))
    step_tick = request.meter.subdivision_tick
    slots_per_bar = max(1, request.meter.bar_ticks // step_tick)
    beat_units = request.meter.bar_ticks / PPQ
    target_count = max(1, round(beat_units * (0.65 + intent.target.density * 1.65)))
    target_count = min(slots_per_bar, target_count)
    kicks = _kick_ticks(request)
    result: list[SkeletonEvent] = []
    motif_positions: list[int] | None = None

    for bar in range(request.bars):
        rng = hrng.stream("rhythm", candidate, bar)
        bar_start = bar * request.meter.bar_ticks
        phrase_index = bar // 4
        phrase_bar = bar % 4
        phrase_id = f"phrase-{phrase_index}"
        motif_id = f"motif-{phrase_index // 2}"
        role_bias = (0.0, -0.05, 0.12, -0.10)[phrase_bar]
        desired = max(1, min(slots_per_bar, round(target_count * (1 + role_bias))))

        if motif_positions is None or phrase_bar == 0:
            scored: list[tuple[float, int]] = []
            for slot in range(slots_per_bar):
                local = slot * step_tick
                tick = bar_start + local
                gravity = _gravity(request, tick)
                relation = _kick_relation(tick, kicks, step_tick)
                kick_score = {
                    "lock": intent.target.kick_lock,
                    "complement": intent.target.kick_complement * 0.82,
                    "answer": intent.target.kick_answer,
                    "anticipate": intent.target.syncopation * 0.64,
                    "independent": 0.15,
                }[relation]
                sync_score = (1 - gravity) * intent.target.syncopation
                anchor_score = gravity * (0.72 + intent.target.root_strength * 0.28)
                noise = float(rng.uniform(-0.16, 0.16)) * (0.2 + intent.target.variation)
                scored.append((anchor_score + kick_score * 0.65 + sync_score * 0.72 + noise, slot))
            selected = {slot for _, slot in sorted(scored, reverse=True)[:desired]}
            if intent.target.root_strength > 0.38:
                selected.add(0)
            motif_positions = sorted(selected)
        else:
            selected = set(motif_positions)
            change_probability = intent.target.variation * (0.18 + phrase_bar * 0.12)
            if rng.random() < change_probability and selected:
                movable = sorted(selected - {0})
                if movable:
                    old = movable[int(rng.integers(0, len(movable)))]
                    direction = -1 if rng.random() < 0.5 else 1
                    new = max(0, min(slots_per_bar - 1, old + direction))
                    selected.remove(old)
                    selected.add(new)
            while len(selected) > desired:
                removable = sorted(selected - {0})
                if not removable:
                    break
                selected.remove(removable[-1])
            while len(selected) < desired:
                choices = [slot for slot in range(slots_per_bar) if slot not in selected]
                if not choices:
                    break
                selected.add(choices[int(rng.integers(0, len(choices)))])

        # Silence is composed separately from onset density. Phrase-end and kick exposure gaps win.
        silence_chance = intent.target.silence * (0.30 if phrase_bar < 3 else 0.48)
        for slot in sorted(selected):
            local = slot * step_tick
            tick = bar_start + local
            gravity = _gravity(request, tick)
            relation = _kick_relation(tick, kicks, step_tick)
            protected = slot == 0 and (bar == 0 or phrase_bar == 0)
            if not protected and rng.random() < silence_chance * (0.45 + gravity * 0.2):
                continue
            role = _role_for_position(
                tick=tick,
                local_tick=local,
                bar=bar,
                bars=request.bars,
                gravity=gravity,
                relation=relation,
                strong=strong,
            )
            index = len(result)
            result.append(
                SkeletonEvent(
                    event_id=hrng.id("bass-event", candidate, bar, slot, index),
                    tick=tick,
                    bar=bar,
                    role=role,
                    weight=_clamp(gravity * 0.72 + (0.22 if protected else 0.08)),
                    phrase_id=phrase_id,
                    motif_id=motif_id,
                    kick_relation=relation,
                )
            )
    return sorted(result, key=lambda event: (event.tick, event.event_id))


def _pitches_in_register(pitch_classes: set[int], limits: RegisterLimits) -> list[int]:
    return [
        pitch
        for pitch in range(limits.lowest_midi_note, limits.highest_midi_note + 1)
        if pitch % 12 in pitch_classes
    ]


def _sample_softmax(
    candidates: list[int], scores: list[float], temperature: float, rng: np.random.Generator
) -> int:
    values = np.asarray(scores, dtype=float)
    values = (values - np.max(values)) / max(0.08, temperature)
    probabilities = np.exp(np.clip(values, -30, 30))
    probabilities /= probabilities.sum()
    return int(rng.choice(np.asarray(candidates), p=probabilities))


def _assign_pitches(
    skeleton: list[SkeletonEvent],
    timeline: HarmonyTimeline,
    intent: BassIntent,
    limits: RegisterLimits,
    hrng: HierarchicalRNG,
    candidate: int,
    input_mode: InputMode,
    preset: str,
) -> None:
    previous: int | None = None
    direction = 1
    for index, item in enumerate(skeleton):
        harmony = harmony_at(timeline, item.tick)
        chord = harmony.chord
        scale_pcs = scale_pitch_classes(harmony.key_context)
        if chord:
            stable_pcs = set(chord.pitch_classes)
            root_pc = (chord.bass_note or chord.root).pitch_class
        else:
            root_pc = harmony.key_context.tonic.pitch_class if harmony.key_context else 0
            stable_pcs = {root_pc, (root_pc + 7) % 12}
        allowed_pcs = stable_pcs | scale_pcs
        candidates_for_pitch = _pitches_in_register(allowed_pcs, limits)
        if not candidates_for_pitch:
            candidates_for_pitch = list(
                range(limits.lowest_midi_note, limits.highest_midi_note + 1)
            )
        rng = hrng.stream("pitch", candidate, item.bar, index)
        phrase_position = (
            item.bar % 4
            + (item.tick % max(1, timeline.events[0].duration_tick))
            / max(1, timeline.events[0].duration_tick)
        ) / 4
        contour = math.sin(phrase_position * math.pi)
        contour_target = (
            limits.preferred_center + contour * intent.target.register_motion * 8 * direction
        )
        scores: list[float] = []
        for pitch in candidates_for_pitch:
            pc = pitch % 12
            harmonic = 1.15 if pc in stable_pcs else 0.25
            root_bonus = 1.4 * intent.target.root_strength if pc == root_pc else 0
            chord_bonus = (
                intent.target.chord_tone_strength if chord and pc in chord.pitch_classes else 0
            )
            voice = 0.4 if previous is None else max(-0.8, 0.75 - abs(pitch - previous) / 8)
            step_bonus = (
                0.0
                if previous is None
                else (intent.target.stepwise_motion * 0.52 if abs(pitch - previous) <= 2 else 0)
            )
            leap_penalty = (
                0.0
                if previous is None
                else max(0, abs(pitch - previous) - limits.max_single_leap) * 0.20
            )
            register = max(-1.0, 0.6 - abs(pitch - contour_target) / 15)
            stable_role = (
                0.35
                if item.role in (RhythmicRole.ANCHOR, RhythmicRole.RECOVERY) and pc in stable_pcs
                else 0
            )
            pedal_bonus = 1.8 if preset == "Pedal" and pc == root_pc else 0
            scores.append(
                harmonic
                + root_bonus
                + chord_bonus
                + voice * (1 - intent.target.melodic_motion * 0.35)
                + step_bonus
                + register
                + stable_role
                + pedal_bonus
                - leap_penalty
            )
        temperature = 0.18 + intent.target.variation * 0.75 + candidate * 0.04
        item.pitch = _sample_softmax(candidates_for_pitch, scores, temperature, rng)
        item.harmonic_role = role_for_pitch(item.pitch, harmony)
        if item.role in (RhythmicRole.ANCHOR, RhythmicRole.RECOVERY) and item.pitch % 12 == root_pc:
            item.harmonic_role = (
                HarmonicRole.STRUCTURAL_ROOT
                if item.role == RhythmicRole.RECOVERY
                else HarmonicRole.ROOT
            )
        if previous is not None and abs(item.pitch - previous) > limits.max_single_leap:
            alternatives = [
                pitch
                for pitch in candidates_for_pitch
                if abs(pitch - previous) <= limits.max_single_leap
            ]
            if alternatives:
                item.pitch = min(alternatives, key=lambda pitch: abs(pitch - contour_target))
                item.harmonic_role = role_for_pitch(item.pitch, harmony)
        previous = item.pitch
        if index and index % 8 == 0:
            direction *= -1

    # Directed approach notes are assigned only when a concrete following target exists.
    for index, (item, target) in enumerate(zip(skeleton, skeleton[1:])):
        rng = hrng.stream("approach", candidate, item.bar, index)
        target_harmony = harmony_at(timeline, target.tick)
        boundary = target_harmony.start_tick == target.tick
        weak = item.role in (
            RhythmicRole.VIOLATION,
            RhythmicRole.ANTICIPATION,
            RhythmicRole.TRANSITION,
        )
        chance = intent.target.approach_activity * (0.72 if boundary else 0.28)
        if (boundary or weak) and rng.random() < chance:
            sign = -1 if rng.random() < 0.5 else 1
            if intent.allow_chromatic_notes and rng.random() < intent.target.chromaticism:
                proposed = target.pitch + sign
                if limits.lowest_midi_note <= proposed <= limits.highest_midi_note:
                    item.pitch = proposed
                    item.harmonic_role = HarmonicRole.CHROMATIC_APPROACH
                    item.approach_target_id = target.event_id
            else:
                harmony = harmony_at(timeline, item.tick)
                scale = scale_pitch_classes(harmony.key_context)
                approaches = [
                    pitch
                    for pitch in range(
                        max(limits.lowest_midi_note, target.pitch - 4),
                        min(limits.highest_midi_note, target.pitch + 4) + 1,
                    )
                    if pitch != target.pitch and pitch % 12 in scale
                ]
                if approaches:
                    item.pitch = min(approaches, key=lambda pitch: abs(pitch - target.pitch))
                    item.harmonic_role = HarmonicRole.APPROACH
                    item.approach_target_id = target.event_id


def _structural_events(
    skeleton: list[SkeletonEvent],
    request: BassGenerateRequest,
    hrng: HierarchicalRNG,
    candidate: int,
) -> list[BassStructuralEvent]:
    result: list[BassStructuralEvent] = []
    pattern_end = request.bars * request.meter.bar_ticks
    boundaries = [0, *(item.tick for item in skeleton), pattern_end]
    for index, (left, right) in enumerate(zip(boundaries, boundaries[1:])):
        gap = right - left
        if gap < PPQ:
            continue
        bar = min(request.bars - 1, left // request.meter.bar_ticks)
        phrase_end = (bar + 1) % 4 == 0
        target = next((item.event_id for item in skeleton if item.tick == right), None)
        if phrase_end:
            role = StructuralRole.PHRASE_BREAK
        elif target and any(abs(right - kick) <= PPQ // 4 for kick in _kick_ticks(request)):
            role = StructuralRole.KICK_EXPOSURE
        else:
            role = StructuralRole.INTENTIONAL_GAP
        result.append(
            BassStructuralEvent(
                event_id=hrng.id("bass-structural", candidate, index, left, right),
                start_tick=left,
                duration_tick=gap,
                role=role,
                target_event_id=target,
                strength=_clamp(gap / (request.meter.bar_ticks * 0.75)),
            )
        )
    return result


def _render_events(
    skeleton: list[SkeletonEvent],
    request: BassGenerateRequest,
    intent: BassIntent,
    hrng: HierarchicalRNG,
    candidate: int,
) -> list[BassEvent]:
    events: list[BassEvent] = []
    end_tick = request.bars * request.meter.bar_ticks
    for index, item in enumerate(skeleton):
        next_tick = skeleton[index + 1].tick if index + 1 < len(skeleton) else end_tick
        available = max(1, next_tick - item.tick)
        # Deliberate silence must not be filled back in by sustaining across every omitted onset.
        phrase_span = max(60, int(PPQ * (1.10 - intent.target.silence * 0.58)))
        duration_space = min(available, phrase_span)
        rng = hrng.stream("performance", candidate, item.bar, index)
        contrast = intent.target.duration_contrast
        base_ratio = 0.48 + (
            0.28 if item.role in (RhythmicRole.ANCHOR, RhythmicRole.RECOVERY) else 0
        )
        ratio = base_ratio + float(rng.uniform(-0.22, 0.22)) * contrast
        if item.bar % 4 == 3 and item.role == RhythmicRole.RECOVERY:
            ratio = max(ratio, 0.86)
        duration = max(60, min(available, int(duration_space * _clamp(ratio))))
        if request.voice_policy == BassVoicePolicy.MONOPHONIC_LEGATO:
            duration = min(available + 30, max(duration, available))
        connection = ConnectionType.STACCATO if ratio < 0.48 else ConnectionType.NORMAL
        if ratio > 0.82:
            connection = ConnectionType.LEGATO
        technique = TechniqueType.GHOST if item.role == RhythmicRole.GHOST else TechniqueType.NORMAL
        accent = AccentType.ACCENT if item.weight > 0.72 else AccentType.NORMAL
        velocity_base = 72 + item.weight * 30
        velocity_noise = float(rng.normal(0, 5)) * intent.target.velocity_contrast
        velocity = max(1, min(127, round(velocity_base + velocity_noise)))
        phrase_contour = math.sin((item.bar % 4) / 3 * math.pi) if item.bar % 4 else 0
        relation_offset = {
            "lock": 1_500,
            "complement": -1_500,
            "answer": 3_500,
            "anticipate": -3_500,
            "independent": 0,
        }[item.kick_relation]
        pocket = 2_800 + relation_offset + phrase_contour * 2_500
        micro = int((pocket + rng.normal(0, 750)) * intent.target.human_feel)
        micro = max(-MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, micro))
        structural = 0
        local_tick = item.tick % request.meter.bar_ticks
        is_triplet_grid = request.meter.subdivisions_per_quarter in (3, 6)
        if not is_triplet_grid and local_tick % (PPQ // 2) == PPQ // 4:
            structural = int((PPQ // 4) * 0.12 * intent.target.human_feel)
        events.append(
            BassEvent(
                event_id=item.event_id,
                grid_tick=item.tick,
                structural_offset_tick=structural,
                micro_offset_us=micro,
                duration_tick=duration,
                pitch=item.pitch,
                velocity=velocity,
                harmonic_role=item.harmonic_role,
                rhythmic_role=item.role,
                articulation=BassArticulation(
                    connection=connection,
                    technique=technique,
                    accent=accent,
                    legato_overlap_tick=30 if connection == ConnectionType.LEGATO else 0,
                ),
                structural_weight=item.weight,
                phrase_id=item.phrase_id,
                motif_id=item.motif_id,
                approach_target_id=item.approach_target_id,
                provenance=EventProvenance(
                    origin="generated", generator_stage="performance", parent_motif_id=item.motif_id
                ),
            )
        )
    return events


def generate_bass_pattern(request: BassGenerateRequest, candidate: int = 0) -> BassPattern:
    if request.groove_context and request.groove_context.meter != request.meter:
        raise ValueError("GrooveContext meter must match bass request meter")
    resolved, resolution_notes = resolve_intent(request.intent)
    timeline, context = build_harmony_timeline(
        harmony=request.harmony,
        bars=request.bars,
        meter=request.meter,
        input_mode=request.input_mode,
        key=request.key,
        mode=request.mode,
    )
    hrng = HierarchicalRNG(request.seed)
    skeleton = _rhythm_skeleton(request, resolved, hrng, candidate)
    _assign_pitches(
        skeleton,
        timeline,
        resolved,
        request.register_limits,
        hrng,
        candidate,
        request.input_mode,
        request.preset,
    )
    events = _render_events(skeleton, request, resolved, hrng, candidate)
    pattern = BassPattern(
        pattern_id=f"bass-{request.seed}-{candidate}",
        name=f"{request.preset} Bass {candidate + 1}",
        bpm=request.bpm,
        bars=request.bars,
        meter=request.meter,
        tempo_map=TempoMap(segments=[TempoSegment(start_tick=0, bpm=request.bpm)]),
        harmony=timeline,
        key_context=context,
        input_mode=request.input_mode,
        events=events,
        structural_events=_structural_events(skeleton, request, hrng, candidate),
        intent=request.intent,
        register_limits=request.register_limits,
        voice_policy=request.voice_policy,
        metadata=BassPatternMetadata(
            master_seed=request.seed,
            preset=request.preset,
            candidate_index=candidate,
            resolved_intent_notes=resolution_notes,
        ),
        groove_context=request.groove_context,
    )
    attach_decision_traces(pattern)
    pattern.analysis = analyze_bass_pattern(pattern)
    return pattern


def _candidate_distance(left: BassPattern, right: BassPattern) -> float:
    if not left.analysis or not right.analysis:
        return 0
    left_a, right_a = left.analysis.atomic, right.analysis.atomic
    feature_distance = (
        sum(
            abs(a - b)
            for a, b in (
                (left_a.root_ratio, right_a.root_ratio),
                (left_a.syncopation_index, right_a.syncopation_index),
                (left_a.onset_density, right_a.onset_density),
                (left_a.register_mean / 127, right_a.register_mean / 127),
                (left_a.chromatic_ratio, right_a.chromatic_ratio),
            )
        )
        / 5
    )
    left_ticks = {event.grid_tick for event in left.events}
    right_ticks = {event.grid_tick for event in right.events}
    rhythm_distance = 1 - len(left_ticks & right_ticks) / max(1, len(left_ticks | right_ticks))
    return 0.6 * feature_distance + 0.4 * rhythm_distance


def preference_guided_bass_request(
    request: BassGenerateRequest, preference: BassPreferenceSummary | None
) -> tuple[BassGenerateRequest, PreferenceGuidance]:
    disabled = (
        frozenset({"chromatic_tolerance"})
        if not request.intent.allow_chromatic_notes
        else frozenset()
    )
    guidance = guided_feature_values(
        request.intent.target.model_dump(),
        BASS_PREFERENCE_TARGETS,
        preference,
        disabled_features=disabled,
    )
    guided = request.model_copy(deep=True)
    for target, value in guidance.values.items():
        setattr(guided.intent.target, target, value)
    return guided, guidance


def generate_preference_search_bass_pattern(
    request: BassGenerateRequest,
    *,
    candidate: int,
    preference: BassPreferenceSummary | None,
) -> BassPattern:
    guided_request, guidance = preference_guided_bass_request(request, preference)
    use_guidance = guidance.active and candidate % 2 == 1
    pattern = generate_bass_pattern(
        guided_request if use_guidance else request,
        candidate=candidate,
    )
    if not use_guidance:
        return pattern
    pattern.intent = request.intent.model_copy(deep=True)
    pattern.metadata.preference_guided = True
    pattern.metadata.preference_guidance_strength = guidance.strength
    pattern.metadata.preference_guided_features = list(guidance.features)
    _, original_resolution_notes = resolve_intent(request.intent)
    pattern.metadata.resolved_intent_notes = original_resolution_notes + [
        "Preference-guided search adjusted " + ", ".join(guidance.features)
    ]
    attach_decision_traces(pattern)
    pattern.analysis = analyze_bass_pattern(pattern)
    return pattern


def generate_bass_candidate_pool(
    request: BassGenerateRequest, preference: BassPreferenceSummary | None = None
) -> list[BassPattern]:
    pool_size = min(10, max(request.candidate_count * 2, request.candidate_count))
    return [
        generate_preference_search_bass_pattern(
            request,
            candidate=index,
            preference=preference,
        )
        for index in range(pool_size)
    ]


def generate_bass_candidates(
    request: BassGenerateRequest, preference: BassPreferenceSummary | None = None
) -> list[BassPattern]:
    pool = generate_bass_candidate_pool(request, preference)
    pool.sort(key=lambda item: blended_candidate_score(item, preference), reverse=True)
    selected = [pool.pop(0)]
    while pool and len(selected) < request.candidate_count:
        choice = max(
            pool,
            key=lambda item: blended_candidate_score(item, preference) * 0.75
            + min(_candidate_distance(item, other) for other in selected) * 0.25,
        )
        selected.append(choice)
        pool.remove(choice)
    return selected
