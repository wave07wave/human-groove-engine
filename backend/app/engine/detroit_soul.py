from __future__ import annotations

from dataclasses import dataclass, fields

from app.config import DRUM_PITCHES, MAX_MICROTIMING_US, PPQ
from app.models.event import DurationStyle, EventRole, GrooveEvent, InstrumentID
from app.models.groove import DetroitSoulSettings
from app.models.meter import MeterDefinition
from app.random.seeds import HierarchicalRNG

from .pulse import strong_positions


@dataclass(frozen=True)
class DetroitSoulProfile:
    timing_kick_us: float
    timing_snare_us: float
    timing_hat_us: float
    timing_jitter_us: float
    timing_base_mix: float
    velocity_kick: float
    velocity_snare: float
    velocity_hat: float
    velocity_jitter: float
    backbeat_boost: float
    hat_accent_boost: float
    kick_keep: float
    kick_add_probability: float
    snare_keep: float
    hat_keep: float
    open_hat_scale: float
    ghost_probability: float
    fill_probability: float
    fill_length: float
    bar_variation: float
    phrase_tension: float
    resolution_strength: float
    space: float
    kick_snare_coordination: float


PROFILES: dict[str, DetroitSoulProfile] = {
    "benny": DetroitSoulProfile(
        timing_kick_us=-2_600,
        timing_snare_us=-900,
        timing_hat_us=-3_300,
        timing_jitter_us=750,
        timing_base_mix=0.18,
        velocity_kick=6,
        velocity_snare=5,
        velocity_hat=1,
        velocity_jitter=3.8,
        backbeat_boost=7,
        hat_accent_boost=5,
        kick_keep=0.97,
        kick_add_probability=0.3,
        snare_keep=0.96,
        hat_keep=0.9,
        open_hat_scale=0.82,
        ghost_probability=0.48,
        fill_probability=0.42,
        fill_length=3.2,
        bar_variation=0.34,
        phrase_tension=0.9,
        resolution_strength=0.95,
        space=0.18,
        kick_snare_coordination=0.9,
    ),
    "pistol": DetroitSoulProfile(
        timing_kick_us=-300,
        timing_snare_us=4_200,
        timing_hat_us=-700,
        timing_jitter_us=2_250,
        timing_base_mix=0.3,
        velocity_kick=2,
        velocity_snare=8,
        velocity_hat=9,
        velocity_jitter=5.2,
        backbeat_boost=12,
        hat_accent_boost=14,
        kick_keep=0.92,
        kick_add_probability=0.22,
        snare_keep=0.98,
        hat_keep=0.96,
        open_hat_scale=1.14,
        ghost_probability=0.68,
        fill_probability=0.34,
        fill_length=3.8,
        bar_variation=0.55,
        phrase_tension=0.78,
        resolution_strength=0.88,
        space=0.2,
        kick_snare_coordination=0.78,
    ),
    "uriel": DetroitSoulProfile(
        timing_kick_us=2_500,
        timing_snare_us=8_800,
        timing_hat_us=3_100,
        timing_jitter_us=1_650,
        timing_base_mix=0.22,
        velocity_kick=7,
        velocity_snare=11,
        velocity_hat=-4,
        velocity_jitter=4.5,
        backbeat_boost=14,
        hat_accent_boost=6,
        kick_keep=0.78,
        kick_add_probability=0.1,
        snare_keep=0.84,
        hat_keep=0.67,
        open_hat_scale=0.62,
        ghost_probability=1.0,
        fill_probability=0.16,
        fill_length=2.1,
        bar_variation=0.28,
        phrase_tension=0.62,
        resolution_strength=0.92,
        space=0.62,
        kick_snare_coordination=0.58,
    ),
}


def resolve_profile(settings: DetroitSoulSettings) -> DetroitSoulProfile | None:
    if settings.mode == "standard":
        return None
    if settings.mode != "blend":
        return PROFILES[settings.mode]
    raw = {
        "benny": settings.blend.benny,
        "pistol": settings.blend.pistol,
        "uriel": settings.blend.uriel,
    }
    total = sum(raw.values())
    weights = {name: value / total for name, value in raw.items()}
    return DetroitSoulProfile(
        **{
            field.name: sum(
                getattr(PROFILES[name], field.name) * weight for name, weight in weights.items()
            )
            for field in fields(DetroitSoulProfile)
        }
    )


def _backbeat_ticks(meter: MeterDefinition) -> list[int]:
    if meter.denominator == 8:
        strong = strong_positions(meter)
        targets = strong[1::2] or strong[-1:]
    elif meter.numerator == 3:
        targets = [PPQ]
    else:
        targets = [tick for tick in (PPQ, 3 * PPQ) if tick < meter.bar_ticks]
    legal_ticks = range(0, meter.bar_ticks, meter.subdivision_tick)
    return sorted(
        {
            min(legal_ticks, key=lambda legal: (abs(legal - target), legal))
            for target in targets
            if target > 0
        }
    )


def _clamp_velocity(value: float) -> int:
    return max(1, min(127, round(value)))


def _new_event(
    *,
    hrng: HierarchicalRNG,
    candidate: int,
    instrument: InstrumentID,
    bar: int,
    slot: int,
    tick: int,
    role: EventRole,
    velocity: int,
    micro_offset_us: int,
    accent: float,
    origin: str = "generated",
) -> GrooveEvent:
    return GrooveEvent(
        event_id=hrng.id("detroit-soul-event", candidate, instrument.value, bar, slot, role.value),
        instrument=instrument,
        grid_tick=tick,
        structural_offset_tick=0,
        micro_offset_us=micro_offset_us,
        duration_tick=150 if instrument != InstrumentID.CLOSED_HAT else 90,
        velocity=_clamp_velocity(velocity),
        pitch=DRUM_PITCHES[instrument.value],
        primary_role=role,
        accent=max(0, min(1, accent)),
        duration_style=DurationStyle.STACCATO,
        choke_group="hihat"
        if instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT)
        else None,
        origin=origin,
    )


def apply_detroit_soul_style(
    events: list[GrooveEvent],
    *,
    settings: DetroitSoulSettings,
    hrng: HierarchicalRNG,
    candidate: int,
    bpm: float,
    bars: int,
    meter: MeterDefinition,
    microtiming_amount: float,
) -> list[GrooveEvent]:
    """Apply a probabilistic performance language, never a recorded phrase or transcription."""
    profile = resolve_profile(settings)
    if profile is None:
        # This early return is deliberate: Standard output stays byte-for-byte
        # identical at the event level to releases before this layer existed.
        return events

    tempo_time = max(0.68, min(1.32, 104 / bpm))
    tempo_density = max(0.72, min(1.18, 108 / bpm))
    expression = 0.48 + 0.52 * microtiming_amount
    backbeats = set(_backbeat_ticks(meter))
    step_tick = meter.subdivision_tick
    transformed: list[GrooveEvent] = []

    for event in events:
        bar = event.grid_tick // meter.bar_ticks
        local = event.grid_tick % meter.bar_ticks
        if event.instrument == InstrumentID.BASS:
            # A drummer profile may reshape the kick topology, but it must not
            # humanize or re-voice the separate bass performance itself.
            transformed.append(event)
            continue
        rng = hrng.stream(
            "detroit-soul-transform", candidate, settings.mode, event.instrument.value, bar, local
        )
        is_recovery = event.primary_role == EventRole.RECOVERY
        is_downbeat = local == 0
        keep = 1.0
        if event.instrument == InstrumentID.KICK and not (is_downbeat or is_recovery):
            keep = profile.kick_keep - profile.space * (0.12 if local in backbeats else 0.2)
        elif event.instrument == InstrumentID.SNARE and not (
            local in backbeats or is_recovery
        ):
            keep = profile.snare_keep
            if event.primary_role == EventRole.GHOST:
                keep *= 0.65 + 0.35 * profile.ghost_probability
        elif event.instrument == InstrumentID.CLOSED_HAT and not is_downbeat:
            keep = profile.hat_keep * tempo_density
            if local in backbeats:
                keep *= 1 - 0.18 * profile.space
        elif event.instrument == InstrumentID.OPEN_HAT:
            keep = min(1.0, profile.open_hat_scale * tempo_density)
        elif event.instrument == InstrumentID.PERCUSSION:
            keep = 1 - 0.45 * profile.space
        if float(rng.random()) > max(0.05, min(1.0, keep)):
            continue

        if event.instrument == InstrumentID.KICK:
            target_timing = profile.timing_kick_us
            velocity_offset = profile.velocity_kick
        elif event.instrument == InstrumentID.SNARE:
            target_timing = profile.timing_snare_us
            velocity_offset = profile.velocity_snare
        elif event.instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT):
            target_timing = profile.timing_hat_us
            velocity_offset = profile.velocity_hat
        else:
            target_timing = (profile.timing_kick_us + profile.timing_snare_us) / 2
            velocity_offset = 0

        jitter = float(rng.normal(0, profile.timing_jitter_us))
        micro = (
            profile.timing_base_mix * event.micro_offset_us
            + expression * tempo_time * (target_timing + jitter)
        )
        accent = event.accent
        velocity = event.velocity + velocity_offset + float(rng.normal(0, profile.velocity_jitter))
        if event.instrument == InstrumentID.SNARE and local in backbeats:
            velocity += profile.backbeat_boost
            accent = min(1.0, accent + profile.backbeat_boost / 55)
        if event.instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT):
            sixteenth = local // max(1, PPQ // 4)
            # Alternating weight plus extra lift immediately before/after a
            # backbeat gives the hat and snare independent conversational arcs.
            hat_accent = 1.0 if sixteenth % 4 in (0, 2) else -0.4
            near_backbeat = any(abs(local - target) == step_tick for target in backbeats)
            if near_backbeat:
                hat_accent += 0.55 * profile.kick_snare_coordination
            velocity += hat_accent * profile.hat_accent_boost
            accent = min(1.0, max(0.0, accent + hat_accent * profile.hat_accent_boost / 60))
        if event.primary_role == EventRole.GHOST:
            velocity = min(velocity, 48 + 8 * (1 - profile.space))

        transformed.append(
            event.model_copy(
                update={
                    "micro_offset_us": max(
                        -MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, round(micro))
                    ),
                    "velocity": _clamp_velocity(velocity),
                    "accent": accent,
                }
            )
        )

    occupied = {(event.instrument, event.grid_tick) for event in transformed}
    drum_occupied = {
        event.grid_tick
        for event in transformed
        if event.instrument in (InstrumentID.KICK, InstrumentID.SNARE)
    }

    for bar in range(bars):
        bar_start = bar * meter.bar_ticks
        bar_rng = hrng.stream("detroit-soul-bar", candidate, settings.mode, bar)
        bar_shape = 1 + float(bar_rng.normal(0, profile.bar_variation * 0.22))
        phrase_end = bar == bars - 1 or bar % 4 == 3

        # Some legal subdivision choices cannot represent the meter's exact
        # mathematical group boundary. In that case the snapped backbeat is
        # made explicit instead of emitting ornaments between grid cells.
        for local in backbeats:
            tick = bar_start + local
            if (InstrumentID.SNARE, tick) in occupied:
                continue
            anchor_rng = hrng.stream(
                "detroit-soul-backbeat", candidate, settings.mode, bar, local
            )
            timing = round(
                expression
                * tempo_time
                * (
                    profile.timing_snare_us
                    + float(anchor_rng.normal(0, profile.timing_jitter_us))
                )
            )
            transformed.append(
                _new_event(
                    hrng=hrng,
                    candidate=candidate,
                    instrument=InstrumentID.SNARE,
                    bar=bar,
                    slot=local // step_tick,
                    tick=tick,
                    role=EventRole.ANCHOR,
                    velocity=round(
                        96
                        + profile.velocity_snare
                        + profile.backbeat_boost
                        + float(anchor_rng.normal(0, profile.velocity_jitter))
                    ),
                    micro_offset_us=max(
                        -MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, timing)
                    ),
                    accent=min(1.0, 0.9 + profile.backbeat_boost / 55),
                )
            )
            occupied.add((InstrumentID.SNARE, tick))
            drum_occupied.add(tick)

        # Sparse kick answers are selected from legal grid positions and
        # suppressed around existing snare hits according to the profile.
        snare_locals = [
            event.grid_tick - bar_start
            for event in transformed
            if event.instrument == InstrumentID.SNARE
            and event.grid_tick // meter.bar_ticks == bar
            and event.primary_role != EventRole.GHOST
        ]
        for slot, local in enumerate(range(step_tick, meter.bar_ticks, step_tick), start=1):
            tick = bar_start + local
            if tick in drum_occupied or local in backbeats or local % PPQ == 0:
                continue
            gravity_bias = 1.0 if local % (PPQ // 2) else 0.55
            probability = (
                profile.kick_add_probability
                * bar_shape
                * tempo_density
                * gravity_bias
                / max(2.8, meter.subdivisions_per_quarter)
            )
            nearest_snare = min(
                (abs(local - snare_local) for snare_local in snare_locals),
                default=PPQ,
            )
            if nearest_snare <= 2 * step_tick:
                probability *= 0.65 + 0.75 * profile.kick_snare_coordination
            else:
                probability *= 1.1 - 0.25 * profile.kick_snare_coordination
            if float(bar_rng.random()) >= probability:
                continue
            if nearest_snare <= step_tick and float(bar_rng.random()) < profile.space:
                continue
            timing = round(
                expression
                * tempo_time
                * (profile.timing_kick_us + float(bar_rng.normal(0, profile.timing_jitter_us)))
            )
            transformed.append(
                _new_event(
                    hrng=hrng,
                    candidate=candidate,
                    instrument=InstrumentID.KICK,
                    bar=bar,
                    slot=slot,
                    tick=tick,
                    role=EventRole.CONFIRMATION,
                    velocity=86 + round(profile.velocity_kick + float(bar_rng.normal(0, 5))),
                    micro_offset_us=max(-MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, timing)),
                    accent=0.62,
                )
            )
            occupied.add((InstrumentID.KICK, tick))
            drum_occupied.add(tick)

        # Ghost notes live around, rather than on, the backbeat. Their random
        # choice and velocity are derived from the seed, not from any source performance.
        ghost_candidates = sorted(
            {
                target + delta
                for target in backbeats
                for delta in (-2 * step_tick, -step_tick, step_tick)
                if 0 <= target + delta < meter.bar_ticks
            }
        )
        for local in ghost_candidates:
            tick = bar_start + local
            if tick in drum_occupied:
                continue
            probability = (
                0.11
                * profile.ghost_probability
                * bar_shape
                * tempo_density
                * (1.12 if local % PPQ else 0.6)
            )
            if float(bar_rng.random()) >= probability:
                continue
            timing = round(
                expression
                * tempo_time
                * (profile.timing_snare_us + float(bar_rng.normal(0, profile.timing_jitter_us)))
            )
            transformed.append(
                _new_event(
                    hrng=hrng,
                    candidate=candidate,
                    instrument=InstrumentID.SNARE,
                    bar=bar,
                    slot=local // step_tick,
                    tick=tick,
                    role=EventRole.GHOST,
                    velocity=29 + round(float(bar_rng.uniform(0, 13))),
                    micro_offset_us=max(-MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, timing)),
                    accent=0.2,
                )
            )
            occupied.add((InstrumentID.SNARE, tick))
            drum_occupied.add(tick)

        fill_probability = profile.fill_probability * (0.35 + 0.65 * phrase_end)
        fill_probability *= 0.78 + 0.32 * profile.phrase_tension
        if float(bar_rng.random()) < min(0.85, fill_probability * bar_shape * tempo_density):
            fill_steps = max(1, round(profile.fill_length + float(bar_rng.uniform(-1, 1))))
            start_slot = max(1, meter.bar_ticks // step_tick - fill_steps)
            for slot in range(start_slot, meter.bar_ticks // step_tick):
                tick = bar_start + slot * step_tick
                if tick in drum_occupied and slot != start_slot:
                    continue
                progress = (slot - start_slot + 1) / max(1, fill_steps)
                instrument = (
                    InstrumentID.SNARE
                    if float(bar_rng.random()) < 0.72
                    else InstrumentID.KICK
                )
                if (instrument, tick) in occupied:
                    continue
                timing_mean = (
                    profile.timing_snare_us
                    if instrument == InstrumentID.SNARE
                    else profile.timing_kick_us
                )
                timing = round(
                    expression
                    * tempo_time
                    * (timing_mean + float(bar_rng.normal(0, profile.timing_jitter_us)))
                )
                velocity = 65 + 25 * progress + (
                    profile.velocity_snare
                    if instrument == InstrumentID.SNARE
                    else profile.velocity_kick
                )
                transformed.append(
                    _new_event(
                        hrng=hrng,
                        candidate=candidate,
                        instrument=instrument,
                        bar=bar,
                        slot=slot,
                        tick=tick,
                        role=EventRole.TRANSITION,
                        velocity=round(velocity + float(bar_rng.normal(0, 5))),
                        micro_offset_us=max(
                            -MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, timing)
                        ),
                        accent=0.5 + 0.35 * progress,
                    )
                )
                occupied.add((instrument, tick))
                drum_occupied.add(tick)

    # Make the final recovery unequivocal without requiring a copied cadence.
    final_bar = bars - 1
    final_target = strong_positions(meter)[-1]
    for index, event in enumerate(transformed):
        if (
            event.instrument == InstrumentID.KICK
            and event.grid_tick // meter.bar_ticks == final_bar
            and event.grid_tick % meter.bar_ticks >= final_target
        ):
            transformed[index] = event.model_copy(
                update={
                    "velocity": _clamp_velocity(
                        event.velocity + 7 * profile.resolution_strength
                    ),
                    "accent": min(1.0, event.accent + 0.12 * profile.resolution_strength),
                }
            )

    final_kick_ticks = {
        event.grid_tick for event in transformed if event.instrument == InstrumentID.KICK
    }
    transformed = [
        event
        for event in transformed
        if not (
            event.instrument == InstrumentID.BASS
            and event.primary_role == EventRole.CONFIRMATION
            and event.grid_tick not in final_kick_ticks
        )
    ]

    return sorted(
        transformed,
        key=lambda event: (event.grid_tick, event.instrument.value, event.event_id),
    )
