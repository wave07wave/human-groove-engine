from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_left
from dataclasses import dataclass, fields
from statistics import mean, pstdev

from app.bass.harmony import build_harmony_timeline, harmony_at, scale_pitch_classes
from app.bass.models import InputMode, ScaleMode, TempoMap, TempoSegment
from app.config import MAX_MICROTIMING_US, PPQ
from app.engine.pulse import strong_positions
from app.random.seeds import HierarchicalRNG

from .models import (
    KEYBOARD_ANALYSIS_VERSION,
    KEYBOARD_GENERATION_VERSION,
    DetroitKeyboardSettings,
    KeyboardAnalysis,
    KeyboardEvent,
    KeyboardGenerateRequest,
    KeyboardInstrument,
    KeyboardPattern,
    KeyboardPatternMetadata,
)


@dataclass(frozen=True)
class KeyboardPerformanceProfile:
    density: float
    offbeat_probability: float
    triplet_probability: float
    anticipation_probability: float
    fill_probability: float
    grace_probability: float
    left_hand_probability: float
    melodic_probability: float
    open_voicing_probability: float
    staccato_probability: float
    tenuto_probability: float
    context_lock: float
    context_complement: float
    velocity_center: float
    velocity_spread: float
    timing_center_us: float
    timing_spread_us: float
    register_center: float
    duration_ratio: float
    ending_pickup_probability: float
    ending_triplet_probability: float
    resolution_duration_ratio: float
    resolution_accent: float


STANDARD_PROFILE = KeyboardPerformanceProfile(
    density=0.38,
    offbeat_probability=0.25,
    triplet_probability=0.02,
    anticipation_probability=0.08,
    fill_probability=0.10,
    grace_probability=0.01,
    left_hand_probability=0.22,
    melodic_probability=0.14,
    open_voicing_probability=0.28,
    staccato_probability=0.18,
    tenuto_probability=0.35,
    context_lock=0.42,
    context_complement=0.28,
    velocity_center=82,
    velocity_spread=5,
    timing_center_us=500,
    timing_spread_us=500,
    register_center=62,
    duration_ratio=0.68,
    ending_pickup_probability=0.22,
    ending_triplet_probability=0.18,
    resolution_duration_ratio=0.78,
    resolution_accent=8,
)

STYLE_PROFILES = {
    "earl": KeyboardPerformanceProfile(
        density=0.58,
        offbeat_probability=0.52,
        triplet_probability=0.05,
        anticipation_probability=0.34,
        fill_probability=0.18,
        grace_probability=0.06,
        left_hand_probability=0.78,
        melodic_probability=0.18,
        open_voicing_probability=0.32,
        staccato_probability=0.42,
        tenuto_probability=0.30,
        context_lock=0.78,
        context_complement=0.22,
        velocity_center=102,
        velocity_spread=8,
        timing_center_us=-550,
        timing_spread_us=850,
        register_center=55,
        duration_ratio=0.52,
        ending_pickup_probability=0.38,
        ending_triplet_probability=0.12,
        resolution_duration_ratio=0.56,
        resolution_accent=18,
    ),
    "joe": KeyboardPerformanceProfile(
        density=0.66,
        offbeat_probability=0.58,
        triplet_probability=0.52,
        anticipation_probability=0.28,
        fill_probability=0.34,
        grace_probability=0.30,
        left_hand_probability=0.58,
        melodic_probability=0.38,
        open_voicing_probability=0.25,
        staccato_probability=0.25,
        tenuto_probability=0.36,
        context_lock=0.48,
        context_complement=0.54,
        velocity_center=91,
        velocity_spread=13,
        timing_center_us=1_800,
        timing_spread_us=1_650,
        register_center=59,
        duration_ratio=0.60,
        ending_pickup_probability=0.76,
        ending_triplet_probability=0.82,
        resolution_duration_ratio=0.72,
        resolution_accent=10,
    ),
    "johnny": KeyboardPerformanceProfile(
        density=0.42,
        offbeat_probability=0.38,
        triplet_probability=0.12,
        anticipation_probability=0.20,
        fill_probability=0.42,
        grace_probability=0.12,
        left_hand_probability=0.14,
        melodic_probability=0.72,
        open_voicing_probability=0.68,
        staccato_probability=0.10,
        tenuto_probability=0.62,
        context_lock=0.32,
        context_complement=0.76,
        velocity_center=76,
        velocity_spread=7,
        timing_center_us=900,
        timing_spread_us=1_050,
        register_center=72,
        duration_ratio=0.82,
        ending_pickup_probability=0.24,
        ending_triplet_probability=0.34,
        resolution_duration_ratio=0.96,
        resolution_accent=3,
    ),
}

INSTRUMENT_WEIGHTS: dict[str, dict[KeyboardInstrument, float]] = {
    "standard": {
        "acoustic_piano": 0.72,
        "tonewheel_organ": 0.12,
        "electric_piano": 0.14,
        "celeste": 0.02,
    },
    "earl": {
        "acoustic_piano": 0.67,
        "tonewheel_organ": 0.27,
        "electric_piano": 0.05,
        "celeste": 0.01,
    },
    "joe": {
        "acoustic_piano": 0.76,
        "tonewheel_organ": 0.19,
        "electric_piano": 0.04,
        "celeste": 0.01,
    },
    "johnny": {
        "acoustic_piano": 0.25,
        "tonewheel_organ": 0.26,
        "electric_piano": 0.34,
        "celeste": 0.15,
    },
}

_MAX_PATTERN_ID_LENGTH = 200
_REVISION_SUFFIX_RESERVE = 22  # "-r" plus room for a 20-digit revision.
_SHORT_ID_DIGEST_LENGTH = 12


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _regenerated_pattern_id(pattern_id: str, revision: int) -> str:
    base = re.sub(r"(?:-r\d+)+$", "", pattern_id)
    reserved_base_length = _MAX_PATTERN_ID_LENGTH - _REVISION_SUFFIX_RESERVE
    if len(base) > reserved_base_length:
        digest = hashlib.sha256(base.encode()).hexdigest()[:_SHORT_ID_DIGEST_LENGTH]
        prefix_length = reserved_base_length - len(digest) - 1
        base = f"{base[:prefix_length]}-{digest}"
    suffix = f"-r{revision}"
    if len(base) + len(suffix) > _MAX_PATTERN_ID_LENGTH:
        digest = hashlib.sha256(base.encode()).hexdigest()[:_SHORT_ID_DIGEST_LENGTH]
        prefix_length = _MAX_PATTERN_ID_LENGTH - len(suffix) - len(digest) - 1
        base = f"{base[:prefix_length]}-{digest}"
    return f"{base}{suffix}"


def _pulse_positions(meter) -> tuple[int, ...]:
    """Return the musically perceived pulse starts within one bar."""
    if meter.denominator in {2, 4}:
        step = PPQ * 4 // meter.denominator
        return tuple(range(0, meter.bar_ticks, step))
    return tuple(strong_positions(meter))


def _near_tick(sorted_ticks: list[int], target: int, tolerance: int) -> bool:
    if not sorted_ticks:
        return False
    index = bisect_left(sorted_ticks, target)
    return any(
        abs(sorted_ticks[position] - target) <= tolerance
        for position in (index - 1, index)
        if 0 <= position < len(sorted_ticks)
    )


def _style_weights(settings: DetroitKeyboardSettings) -> dict[str, float]:
    if settings.mode in STYLE_PROFILES:
        return {settings.mode: 1.0}
    if settings.mode == "standard":
        return {"standard": 1.0}
    total = settings.blend.earl + settings.blend.joe + settings.blend.johnny
    return {
        "earl": settings.blend.earl / total,
        "joe": settings.blend.joe / total,
        "johnny": settings.blend.johnny / total,
    }


def profile_for_settings(
    settings: DetroitKeyboardSettings, bpm: float
) -> tuple[KeyboardPerformanceProfile, dict[KeyboardInstrument, float]]:
    weights = _style_weights(settings)
    sources = {"standard": STANDARD_PROFILE, **STYLE_PROFILES}
    values = {
        field.name: sum(
            weights.get(name, 0) * getattr(sources[name], field.name) for name in weights
        )
        for field in fields(KeyboardPerformanceProfile)
    }
    fast = _clamp((bpm - 118) / 110)
    slow = _clamp((78 - bpm) / 48)
    values["density"] = _clamp(values["density"] + slow * 0.04 - fast * 0.17)
    values["fill_probability"] = _clamp(
        values["fill_probability"] + slow * 0.03 - fast * 0.15
    )
    values["grace_probability"] = _clamp(values["grace_probability"] - fast * 0.12)
    values["ending_pickup_probability"] = _clamp(
        values["ending_pickup_probability"] + slow * 0.03 - fast * 0.18
    )
    values["timing_spread_us"] *= max(0.58, min(1.20, (100 / max(30, bpm)) ** 0.5))
    profile = KeyboardPerformanceProfile(**values)
    instruments = {
        instrument: sum(
            weights.get(name, 0) * INSTRUMENT_WEIGHTS[name][instrument] for name in weights
        )
        for instrument in INSTRUMENT_WEIGHTS["standard"]
    }
    return profile, instruments


def _instrument(
    weights: dict[KeyboardInstrument, float], rng
) -> KeyboardInstrument:
    names = list(weights)
    probabilities = [weights[name] for name in names]
    return str(rng.choice(names, p=probabilities))  # type: ignore[return-value]


def _nearest_pitch(pitch_class: int, center: float, low: int = 36, high: int = 96) -> int:
    choices = [pitch for pitch in range(low, high + 1) if pitch % 12 == pitch_class]
    return min(choices, key=lambda pitch: (abs(pitch - center), pitch))


def _pitch_classes(timeline, tick: int) -> tuple[int, list[int]]:
    harmony = harmony_at(timeline, tick)
    if harmony.chord:
        root = (harmony.chord.bass_note or harmony.chord.root).pitch_class
        ordered = [tone.pitch_class for tone in harmony.chord.spelled_tones]
        return root, list(dict.fromkeys(ordered))
    scale = sorted(scale_pitch_classes(harmony.key_context))
    root = harmony.key_context.tonic.pitch_class if harmony.key_context else scale[0]
    return root, [root, scale[2 % len(scale)], scale[4 % len(scale)]]


def _voicing(
    *,
    timeline,
    tick: int,
    profile: KeyboardPerformanceProfile,
    rng,
    role: str,
    previous_top: int | None,
) -> tuple[list[int], str]:
    root, pitch_classes = _pitch_classes(timeline, tick)
    melodic = role in {"fill", "answer"} and rng.random() < profile.melodic_probability
    target_count = 1 if melodic else 3 + int(rng.random() < 0.46)
    selected = pitch_classes[:target_count]
    while len(selected) < target_count:
        selected.append(pitch_classes[len(selected) % len(pitch_classes)])
    pitches = [
        _nearest_pitch(pc, profile.register_center + index * 2.5)
        for index, pc in enumerate(selected)
    ]
    pitches = sorted(set(pitches))
    if melodic:
        candidates = [pitch for pitch in pitches if pitch >= profile.register_center - 4]
        pitch = candidates[-1] if candidates else pitches[-1]
        if previous_top is not None:
            pitch = min(
                [pitch - 12, pitch, pitch + 12],
                key=lambda value: abs(value - previous_top) if 48 <= value <= 96 else 999,
            )
        pitches = [pitch]
    elif rng.random() < profile.open_voicing_probability and len(pitches) >= 3:
        pitches[-1] = min(96, pitches[-1] + 12)
        pitches = sorted(set(pitches))

    left_hand = rng.random() < profile.left_hand_probability
    if left_hand:
        low_root = _nearest_pitch(root, profile.register_center - 15, 32, 64)
        pitches = sorted(set([low_root, *pitches]))
        if profile.left_hand_probability > 0.7 and rng.random() < 0.42:
            octave = low_root + 12
            if octave not in pitches:
                pitches.insert(1, octave)
    hand = "both" if left_hand and max(pitches) >= 60 else "left" if left_hand else "right"
    return pitches[:7], hand


def _candidate_onsets(
    request: KeyboardGenerateRequest,
    profile: KeyboardPerformanceProfile,
    hrng: HierarchicalRNG,
    candidate: int,
) -> list[tuple[int, str]]:
    onsets: dict[int, str] = {}
    eighth = PPQ // 2
    context = request.rhythm_context
    kick_ticks = sorted(set(context.kick_ticks))
    bass_ticks = sorted(set(context.bass_ticks))
    snare_ticks = sorted(set(context.snare_ticks))
    context_tolerance = max(PPQ // 16, min(PPQ // 6, request.meter.subdivision_tick // 2))
    pulse_positions = set(_pulse_positions(request.meter))
    contour = (0.84, 1.02, 1.18, 0.72)
    for bar in range(request.bars):
        bar_start = bar * request.meter.bar_ticks
        bar_end = bar_start + request.meter.bar_ticks
        bar_rng = hrng.stream("keyboard-rhythm", candidate, bar)
        variation = contour[bar % len(contour)]
        for tick in range(bar_start, bar_end, eighth):
            local = tick - bar_start
            strong = local in pulse_positions
            probability = profile.density * variation
            probability *= 0.86 if strong else profile.offbeat_probability
            if local == 0:
                probability = max(probability, 0.92)
            if _near_tick(kick_ticks, tick, context_tolerance):
                probability += 0.22 * profile.context_lock
            if _near_tick(bass_ticks, tick, context_tolerance):
                probability += 0.10 * profile.context_lock - 0.16 * profile.context_complement
            if _near_tick(snare_ticks, tick - eighth, context_tolerance):
                probability += 0.12 * profile.context_complement
            if bar_rng.random() < _clamp(probability):
                if local == 0:
                    role = "anchor"
                elif strong:
                    role = "comp"
                else:
                    role = "answer" if bar_rng.random() < profile.context_complement else "comp"
                if bar_rng.random() < profile.fill_probability * (0.55 if strong else 1.0):
                    role = "fill"
                onsets[tick] = role

        for beat in range(bar_start, bar_end, PPQ):
            triplet = beat + round(PPQ * 2 / 3)
            if (
                triplet < bar_end
                and bar_rng.random() < profile.triplet_probability * profile.density
            ):
                onsets[triplet] = "answer"
        anticipation = bar_end - PPQ // 4
        if anticipation >= bar_start and bar_rng.random() < profile.anticipation_probability:
            onsets[anticipation] = "fill"
        if not any(bar_start <= tick < bar_end for tick in onsets):
            onsets[bar_start] = "anchor"

    final_bar_start = (request.bars - 1) * request.meter.bar_ticks
    final_local_tick = max(pulse_positions)
    final_tick = final_bar_start + final_local_tick
    onsets = {tick: role for tick, role in onsets.items() if tick <= final_tick}
    ending_rng = hrng.stream("keyboard-ending", candidate)
    if final_local_tick > 0 and ending_rng.random() < profile.ending_pickup_probability:
        ordered_pulses = sorted(pulse_positions)
        final_pulse_index = ordered_pulses.index(final_local_tick)
        previous_pulse = ordered_pulses[final_pulse_index - 1]
        pulse_width = final_local_tick - previous_pulse
        if ending_rng.random() < profile.ending_triplet_probability:
            lead = max(request.meter.subdivision_tick, round(pulse_width / 3))
        else:
            lead = max(request.meter.subdivision_tick, pulse_width // 2)
        pickup_tick = final_tick - lead
        if pickup_tick > final_bar_start:
            onsets[pickup_tick] = "fill"
    onsets[final_tick] = "resolution"
    return sorted(onsets.items())


def _render_events(
    request: KeyboardGenerateRequest,
    timeline,
    profile: KeyboardPerformanceProfile,
    instrument_weights: dict[KeyboardInstrument, float],
    hrng: HierarchicalRNG,
    candidate: int,
) -> list[KeyboardEvent]:
    onsets = _candidate_onsets(request, profile, hrng, candidate)
    pattern_end = request.bars * request.meter.bar_ticks
    events: list[KeyboardEvent] = []
    previous_top: int | None = None
    primary_instrument = _instrument(
        instrument_weights, hrng.stream("keyboard-instrument", candidate)
    )
    for index, (tick, role) in enumerate(onsets):
        rng = hrng.stream("keyboard-performance", candidate, tick, role)
        next_tick = onsets[index + 1][0] if index + 1 < len(onsets) else pattern_end
        available = max(60, next_tick - tick)
        pitches, hand = _voicing(
            timeline=timeline,
            tick=tick,
            profile=profile,
            rng=rng,
            role=role,
            previous_top=previous_top,
        )
        previous_top = pitches[-1]
        accent = (
            profile.resolution_accent
            if role == "resolution"
            else 10
            if role == "anchor"
            else 4
            if role == "answer"
            else 0
        )
        velocities = [
            max(
                24,
                min(
                    122,
                    round(
                        profile.velocity_center
                        + accent
                        + rng.normal(0, profile.velocity_spread)
                    ),
                ),
            )
            for _ in pitches
        ]
        if role == "fill":
            velocities = [max(30, velocity - 8) for velocity in velocities]
        if role == "resolution":
            articulation = "tenuto"
            duration = min(
                pattern_end - tick,
                max(60, round(available * profile.resolution_duration_ratio)),
            )
        else:
            roll = rng.random()
            articulation = (
                "staccato"
                if roll < profile.staccato_probability
                else "tenuto"
                if roll < profile.staccato_probability + profile.tenuto_probability
                else "normal"
            )
            ratio = profile.duration_ratio * (0.52 if articulation == "staccato" else 1)
            duration = min(pattern_end - tick, max(60, round(available * ratio)))
        center = profile.timing_center_us
        if tick % PPQ != 0:
            center += 500 if profile.timing_center_us > 0 else -250
        micro = max(
            -MAX_MICROTIMING_US,
            min(MAX_MICROTIMING_US, round(center + rng.normal(0, profile.timing_spread_us))),
        )
        instrument = primary_instrument
        events.append(
            KeyboardEvent(
                event_id=hrng.id("keyboard", candidate, tick, role),
                grid_tick=tick,
                micro_offset_us=micro,
                duration_tick=duration,
                pitches=pitches,
                velocities=velocities,
                instrument=instrument,
                role=role,
                hand=hand,
                articulation=articulation,
            )
        )

        if tick >= PPQ // 4 and role != "resolution" and rng.random() < profile.grace_probability:
            grace_tick = tick - PPQ // 8
            if not any(event.grid_tick == grace_tick for event in events):
                direction = -1 if rng.random() < 0.5 else 1
                grace_pitch = max(36, min(96, pitches[-1] + direction))
                grace_velocity = max(
                    24,
                    min(92, round(profile.velocity_center - 22 + rng.normal(0, 6))),
                )
                events.append(
                    KeyboardEvent(
                        event_id=hrng.id("keyboard-grace", candidate, tick),
                        grid_tick=grace_tick,
                        micro_offset_us=micro,
                        duration_tick=PPQ // 10,
                        pitches=[grace_pitch],
                        velocities=[grace_velocity],
                        instrument=instrument,
                        role="grace",
                        hand="right",
                        articulation="staccato",
                    )
                )
    return sorted(events, key=lambda event: (event.grid_tick, event.event_id))


def analyze_keyboard_pattern(pattern: KeyboardPattern) -> KeyboardAnalysis:
    end_tick = pattern.bars * pattern.meter.bar_ticks
    if not pattern.harmony.events:
        raise ValueError("keyboard harmony timeline cannot be empty")
    harmony_cursor = 0
    for harmony_event in pattern.harmony.events:
        if harmony_event.start_tick != harmony_cursor:
            raise ValueError("keyboard harmony timeline must be continuous from tick zero")
        harmony_cursor = harmony_event.start_tick + harmony_event.duration_tick
    if harmony_cursor != end_tick:
        raise ValueError("keyboard harmony timeline must cover the complete pattern")

    events = pattern.events
    if not events:
        return KeyboardAnalysis(
            onsets_per_bar=0,
            syncopation_ratio=0,
            mean_velocity=0,
            velocity_spread=0,
            timing_mean_us=0,
            timing_spread_us=0,
            register_mean=0,
            voicing_span=0,
            notes_per_onset=0,
            left_hand_ratio=0,
            melodic_ratio=0,
            grace_ratio=0,
            phrase_variation=0,
            context_alignment=0,
            final_resolution=0,
            instrument_distribution={},
        )
    velocities = [velocity for event in events for velocity in event.velocities]
    pitches = [pitch for event in events for pitch in event.pitches]
    spans = [max(event.pitches) - min(event.pitches) for event in events]
    counts = [
        sum(event.grid_tick // pattern.meter.bar_ticks == bar for event in events)
        for bar in range(pattern.bars)
    ]
    context_ticks = sorted(
        set(
            pattern.rhythm_context.kick_ticks
            + pattern.rhythm_context.snare_ticks
            + pattern.rhythm_context.bass_ticks
        )
    )
    context_tolerance = max(PPQ // 16, min(PPQ // 6, pattern.meter.subdivision_tick // 2))
    pulse_positions = set(_pulse_positions(pattern.meter))
    instrument_counts = {
        name: sum(event.instrument == name for event in events)
        for name in INSTRUMENT_WEIGHTS["standard"]
    }
    last = events[-1]
    root, _ = _pitch_classes(pattern.harmony, last.grid_tick)
    return KeyboardAnalysis(
        onsets_per_bar=len(events) / pattern.bars,
        syncopation_ratio=sum(
            event.grid_tick % pattern.meter.bar_ticks not in pulse_positions
            for event in events
        )
        / len(events),
        mean_velocity=mean(velocities),
        velocity_spread=pstdev(velocities),
        timing_mean_us=mean(event.micro_offset_us for event in events),
        timing_spread_us=pstdev(event.micro_offset_us for event in events),
        register_mean=mean(pitches),
        voicing_span=mean(spans),
        notes_per_onset=mean(len(event.pitches) for event in events),
        left_hand_ratio=sum(event.hand in {"left", "both"} for event in events) / len(events),
        melodic_ratio=sum(
            event.role in {"answer", "fill"} and len(event.pitches) == 1
            for event in events
        )
        / len(events),
        grace_ratio=sum(event.role == "grace" for event in events) / len(events),
        phrase_variation=pstdev(counts),
        context_alignment=(
            sum(
                _near_tick(context_ticks, event.grid_tick, context_tolerance)
                for event in events
            )
            / len(events)
            if context_ticks
            else 0
        ),
        final_resolution=float(
            last.role == "resolution" and root in {p % 12 for p in last.pitches}
        ),
        instrument_distribution={
            name: count / len(events) for name, count in instrument_counts.items()
        },
    )


def generate_keyboard_pattern(
    request: KeyboardGenerateRequest, candidate: int = 0
) -> KeyboardPattern:
    timeline, key_context = build_harmony_timeline(
        harmony=request.harmony,
        bars=request.bars,
        meter=request.meter,
        input_mode=InputMode.CHORD_PROGRESSION,
        key=request.key,
        mode=request.mode,
    )
    profile, instrument_weights = profile_for_settings(
        request.detroit_keyboard, request.bpm
    )
    hrng = HierarchicalRNG(request.seed)
    events = _render_events(
        request,
        timeline,
        profile,
        instrument_weights,
        hrng,
        candidate,
    )
    label = {
        "standard": "Standard",
        "earl": "Earl-inspired",
        "joe": "Joe-inspired",
        "johnny": "Johnny-inspired",
        "blend": "Detroit blend",
    }[request.detroit_keyboard.mode]
    fingerprint_payload = request.model_dump(mode="json", exclude={"candidate_count"})
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12]
    pattern = KeyboardPattern(
        pattern_id=f"keys-{request.seed}-{candidate}-{fingerprint}",
        name=f"{label} Keys {candidate + 1}",
        bpm=request.bpm,
        bars=request.bars,
        meter=request.meter,
        tempo_map=TempoMap(segments=[TempoSegment(start_tick=0, bpm=request.bpm)]),
        harmony_text=request.harmony,
        harmony=timeline,
        key_context=key_context,
        events=events,
        rhythm_context=request.rhythm_context.model_copy(deep=True),
        metadata=KeyboardPatternMetadata(
            master_seed=request.seed,
            candidate_index=candidate,
            keyboard_generation_version=KEYBOARD_GENERATION_VERSION,
            keyboard_analysis_version=KEYBOARD_ANALYSIS_VERSION,
            detroit_keyboard=request.detroit_keyboard.model_copy(deep=True),
            generation_notes=[
                "Generative keyboard language only; no recording or source phrase was used."
            ],
        ),
    )
    pattern.analysis = analyze_keyboard_pattern(pattern)
    return pattern


def generate_keyboard_candidates(request: KeyboardGenerateRequest) -> list[KeyboardPattern]:
    return [
        generate_keyboard_pattern(request, candidate=index)
        for index in range(request.candidate_count)
    ]


def regenerate_keyboard_pattern(
    pattern: KeyboardPattern, selected_bars: set[int]
) -> KeyboardPattern:
    bars = selected_bars or set(range(pattern.bars))
    if any(bar < 0 or bar >= pattern.bars for bar in bars):
        raise ValueError("selected keyboard bar outside pattern")
    bars -= set(pattern.bar_locks)
    if not bars:
        return pattern.model_copy(deep=True)
    fresh = generate_keyboard_pattern(
        KeyboardGenerateRequest(
            bpm=pattern.bpm,
            bars=pattern.bars,
            meter=pattern.meter,
            harmony=pattern.harmony_text,
            key=(
                pattern.key_context.tonic.letter
                + "#" * max(0, pattern.key_context.tonic.accidental)
                + "b" * max(0, -pattern.key_context.tonic.accidental)
                if pattern.key_context
                else None
            ),
            mode=pattern.key_context.mode if pattern.key_context else ScaleMode.MAJOR,
            seed=pattern.metadata.master_seed + 1,
            candidate_count=1,
            detroit_keyboard=pattern.metadata.detroit_keyboard,
            rhythm_context=pattern.rhythm_context,
        ),
        candidate=pattern.metadata.candidate_index,
    )
    kept = [
        event
        for event in pattern.events
        if event.locked or event.grid_tick // pattern.meter.bar_ticks not in bars
    ]
    locked_ticks = {event.grid_tick for event in kept if event.locked}
    replacements = [
        event.model_copy(update={"origin": "regenerated"})
        for event in fresh.events
        if event.grid_tick // pattern.meter.bar_ticks in bars
        and event.grid_tick not in locked_ticks
    ]
    result = pattern.model_copy(deep=True)
    result.harmony = fresh.harmony.model_copy(deep=True)
    result.key_context = (
        fresh.key_context.model_copy(deep=True) if fresh.key_context else None
    )
    result.events = sorted(kept + replacements, key=lambda event: (event.grid_tick, event.event_id))
    result.metadata.master_seed += 1
    result.metadata.revision += 1
    result.metadata.keyboard_generation_version = KEYBOARD_GENERATION_VERSION
    result.metadata.keyboard_analysis_version = KEYBOARD_ANALYSIS_VERSION
    result.pattern_id = _regenerated_pattern_id(
        pattern.pattern_id, result.metadata.revision
    )
    result.analysis = analyze_keyboard_pattern(result)
    return KeyboardPattern.model_validate(result.model_dump())
