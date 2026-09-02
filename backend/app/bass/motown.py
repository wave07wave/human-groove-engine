from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from app.config import MAX_MICROTIMING_US
from app.random.seeds import HierarchicalRNG

from .harmony import harmony_at
from .models import (
    AccentType,
    BassEvent,
    BassIntent,
    BassVoicePolicy,
    ConnectionType,
    HarmonicRole,
    HarmonyTimeline,
    MotownBassSettings,
    RegisterLimits,
    RhythmicRole,
    TechniqueType,
)


@dataclass(frozen=True)
class JamersonPerformanceProfile:
    """BPM-resolved targets, never a stored or transcribed phrase."""

    density: float
    syncopation: float
    chromaticism: float
    approach_activity: float
    melodic_motion: float
    stepwise_motion: float
    variation: float
    phrase_development: float
    resolution_strength: float
    human_feel: float
    ghost_probability: float
    mute_probability: float
    anchor_timing_us: int
    syncopated_timing_us: int
    motion_timing_us: int
    timing_spread_us: int
    anchor_velocity: int
    motion_velocity: int
    ghost_velocity: int
    anchor_duration_ratio: float
    motion_duration_ratio: float
    ghost_duration_ratio: float


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _toward(current: float, target: float, strength: float = 0.72) -> float:
    return _clamp(current * (1 - strength) + target * strength)


def jamerson_profile_for_bpm(bpm: float) -> JamersonPerformanceProfile:
    """Reduce ornamental activity as the tempo rises while preserving the pocket."""

    fast = _clamp((bpm - 115) / 95)
    slow = _clamp((82 - bpm) / 52)
    timing_scale = max(0.62, min(1.22, (100 / max(30, bpm)) ** 0.5))
    return JamersonPerformanceProfile(
        density=_clamp(0.66 + slow * 0.05 - fast * 0.16),
        syncopation=_clamp(0.72 + slow * 0.03 - fast * 0.13),
        chromaticism=_clamp(0.54 + slow * 0.04 - fast * 0.17),
        approach_activity=_clamp(0.70 + slow * 0.04 - fast * 0.16),
        melodic_motion=_clamp(0.72 + slow * 0.03 - fast * 0.11),
        stepwise_motion=_clamp(0.82 + slow * 0.02 - fast * 0.08),
        variation=_clamp(0.55 + slow * 0.03 - fast * 0.10),
        phrase_development=_clamp(0.72 + slow * 0.02 - fast * 0.08),
        resolution_strength=_clamp(0.88 - fast * 0.05),
        human_feel=_clamp(0.44 - fast * 0.08),
        ghost_probability=_clamp(0.24 + slow * 0.03 - fast * 0.11),
        mute_probability=_clamp(0.70 - fast * 0.08),
        anchor_timing_us=round(1_450 * timing_scale),
        syncopated_timing_us=round(-1_250 * timing_scale),
        motion_timing_us=round(450 * timing_scale),
        timing_spread_us=round(1_350 * timing_scale),
        anchor_velocity=104,
        motion_velocity=87,
        ghost_velocity=43,
        anchor_duration_ratio=_clamp(0.72 - fast * 0.08),
        motion_duration_ratio=_clamp(0.52 - fast * 0.08),
        ghost_duration_ratio=_clamp(0.20 - fast * 0.04),
    )


def apply_jamerson_intent(
    intent: BassIntent,
    settings: MotownBassSettings,
    bpm: float,
) -> tuple[BassIntent, JamersonPerformanceProfile | None, list[str]]:
    if settings.mode == "standard":
        return intent, None, []

    profile = jamerson_profile_for_bpm(bpm)
    result = deepcopy(intent)
    target = result.target
    target.root_strength = _toward(target.root_strength, 0.58)
    target.chord_tone_strength = _toward(target.chord_tone_strength, 0.86)
    target.chromaticism = (
        _toward(target.chromaticism, profile.chromaticism)
        if result.allow_chromatic_notes
        else 0
    )
    target.approach_activity = _toward(target.approach_activity, profile.approach_activity)
    target.melodic_motion = _toward(target.melodic_motion, profile.melodic_motion)
    target.stepwise_motion = _toward(target.stepwise_motion, profile.stepwise_motion)
    target.leap_activity = _toward(target.leap_activity, 0.24)
    target.register_motion = _toward(target.register_motion, 0.42)
    target.syncopation = _toward(target.syncopation, profile.syncopation)
    target.kick_lock = _toward(target.kick_lock, 0.68)
    target.kick_complement = _toward(target.kick_complement, 0.44)
    target.kick_answer = _toward(target.kick_answer, 0.52)
    target.density = _toward(target.density, profile.density)
    target.silence = _toward(target.silence, 0.22)
    target.duration_contrast = _toward(target.duration_contrast, 0.56)
    target.velocity_contrast = _toward(target.velocity_contrast, 0.48)
    target.repetition = _toward(target.repetition, 0.62)
    target.variation = _toward(target.variation, profile.variation)
    target.phrase_development = _toward(
        target.phrase_development, profile.phrase_development
    )
    target.tension = _toward(target.tension, 0.54)
    target.resolution_strength = _toward(
        target.resolution_strength, profile.resolution_strength
    )
    target.human_feel = _toward(target.human_feel, profile.human_feel)
    return result, profile, [
        "Jamerson-inspired generative layer applied: syncopation, chromatic approach, "
        "melodic motion, muted/ghost articulation and phrase resolution; no source phrase used"
    ]


def _nearest_root(
    event: BassEvent,
    timeline: HarmonyTimeline,
    limits: RegisterLimits,
    previous_pitch: int | None,
) -> int | None:
    harmony = harmony_at(timeline, event.grid_tick)
    if harmony.chord:
        root_pc = (harmony.chord.bass_note or harmony.chord.root).pitch_class
    elif harmony.key_context:
        root_pc = harmony.key_context.tonic.pitch_class
    else:
        return None
    roots = [
        pitch
        for pitch in range(limits.lowest_midi_note, limits.highest_midi_note + 1)
        if pitch % 12 == root_pc
    ]
    if not roots:
        return None
    return min(
        roots,
        key=lambda pitch: (
            abs(pitch - event.pitch)
            + (
                max(0, abs(pitch - previous_pitch) - limits.max_single_leap) * 2
                if previous_pitch is not None
                else 0
            ),
            abs(pitch - limits.preferred_center),
            pitch,
        ),
    )


def apply_jamerson_performance(
    events: list[BassEvent],
    *,
    settings: MotownBassSettings,
    profile: JamersonPerformanceProfile | None,
    bpm: float,
    bars: int,
    bar_ticks: int,
    timeline: HarmonyTimeline,
    limits: RegisterLimits,
    voice_policy: BassVoicePolicy,
    hrng: HierarchicalRNG,
    candidate: int,
) -> list[BassEvent]:
    if settings.mode == "standard" or profile is None:
        return events

    del bpm  # The resolved profile already contains the BPM compensation.
    result = sorted(
        (event.model_copy(deep=True) for event in events),
        key=lambda event: (event.grid_tick, event.event_id),
    )
    pattern_end = bars * bar_ticks
    approach_targets = {event.approach_target_id for event in result if event.approach_target_id}
    weak_roles = {
        RhythmicRole.CONFIRMATION,
        RhythmicRole.ANTICIPATION,
        RhythmicRole.VIOLATION,
        RhythmicRole.DECORATION,
        RhythmicRole.TRANSITION,
    }
    syncopated_roles = {
        RhythmicRole.ANTICIPATION,
        RhythmicRole.VIOLATION,
        RhythmicRole.TRANSITION,
    }

    for index, event in enumerate(result):
        rng = hrng.stream("jamerson-performance", candidate, event.event_id)
        next_tick = result[index + 1].grid_tick if index + 1 < len(result) else pattern_end
        available = max(1, min(pattern_end - event.grid_tick, next_tick - event.grid_tick))
        local_tick = event.grid_tick % bar_ticks
        ghost_weight = 1.35 if event.rhythmic_role in syncopated_roles else 0.62
        ghost_eligible = (
            event.rhythmic_role in weak_roles
            and event.harmonic_role
            not in {HarmonicRole.APPROACH, HarmonicRole.CHROMATIC_APPROACH}
            and event.event_id not in approach_targets
            and local_tick != 0
        )
        is_ghost = ghost_eligible and rng.random() < profile.ghost_probability * ghost_weight

        if is_ghost:
            event.rhythmic_role = RhythmicRole.GHOST
            event.articulation.technique = TechniqueType.GHOST
            event.articulation.connection = ConnectionType.STACCATO
            event.articulation.accent = AccentType.SOFT
            event.articulation.legato_overlap_tick = 0
            event.velocity = max(24, min(62, round(profile.ghost_velocity + rng.normal(0, 5))))
            event.duration_tick = max(
                30,
                min(pattern_end - event.grid_tick, round(available * profile.ghost_duration_ratio)),
            )
            center = profile.motion_timing_us
        else:
            anchor = event.rhythmic_role in {RhythmicRole.ANCHOR, RhythmicRole.RECOVERY}
            if rng.random() < profile.mute_probability:
                event.articulation.technique = TechniqueType.MUTE
            event.articulation.accent = AccentType.ACCENT if anchor else AccentType.NORMAL
            base_velocity = profile.anchor_velocity if anchor else profile.motion_velocity
            if event.harmonic_role in {HarmonicRole.ROOT, HarmonicRole.STRUCTURAL_ROOT}:
                base_velocity += 3
            spread = 3.2 if anchor else 6.5
            event.velocity = max(52, min(118, round(base_velocity + rng.normal(0, spread))))
            ratio = profile.anchor_duration_ratio if anchor else profile.motion_duration_ratio
            event.duration_tick = max(
                45,
                min(pattern_end - event.grid_tick, round(available * ratio)),
            )
            if voice_policy == BassVoicePolicy.MONOPHONIC_LEGATO:
                event.duration_tick = min(
                    pattern_end - event.grid_tick,
                    max(event.duration_tick, available),
                )
                event.articulation.connection = ConnectionType.LEGATO
                event.articulation.legato_overlap_tick = 30
            else:
                event.articulation.connection = (
                    ConnectionType.TENUTO if anchor else ConnectionType.NORMAL
                )
                event.articulation.legato_overlap_tick = 0
            center = (
                profile.anchor_timing_us
                if anchor
                else profile.syncopated_timing_us
                if event.rhythmic_role in syncopated_roles
                else profile.motion_timing_us
            )

        target_micro = center + int(rng.normal(0, profile.timing_spread_us))
        event.micro_offset_us = max(
            -MAX_MICROTIMING_US,
            min(MAX_MICROTIMING_US, round(event.micro_offset_us * 0.34 + target_micro * 0.66)),
        )

    phrase_end_bars = {bar for bar in range(bars) if bar % 4 == 3 or bar == bars - 1}
    for bar in sorted(phrase_end_bars):
        indices = [
            index
            for index, event in enumerate(result)
            if event.grid_tick // bar_ticks == bar
        ]
        if not indices:
            continue
        index = indices[-1]
        event = result[index]
        rng = hrng.stream("jamerson-resolution", candidate, bar, event.event_id)
        if rng.random() >= profile.resolution_strength:
            continue
        previous_pitch = result[index - 1].pitch if index else None
        root = _nearest_root(event, timeline, limits, previous_pitch)
        if root is None:
            continue
        event.pitch = root
        event.harmonic_role = HarmonicRole.STRUCTURAL_ROOT
        event.rhythmic_role = RhythmicRole.RECOVERY
        event.approach_target_id = None
        event.articulation.technique = TechniqueType.MUTE
        event.articulation.connection = ConnectionType.TENUTO
        event.articulation.accent = AccentType.ACCENT
        event.articulation.legato_overlap_tick = 0
        event.velocity = max(event.velocity, profile.anchor_velocity)

    return result
