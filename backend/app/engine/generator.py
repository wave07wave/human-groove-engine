from __future__ import annotations

import math

from app.config import DRUM_PITCHES, INSTRUMENT_OFFSETS_US, MAX_MICROTIMING_US, PPQ
from app.models.event import DurationStyle, EventRole, GrooveEvent, InstrumentID
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.models.pattern import GroovePattern, PatternMetadata
from app.random.seeds import HierarchicalRNG

from .phrase import choose_grammar, motif_for_bar, tension_curve
from .pulse import metric_gravity, strong_positions


def _event(
    hrng: HierarchicalRNG,
    instrument: InstrumentID,
    bar: int,
    slot: int,
    grid_tick: int,
    role: EventRole,
    accent: float,
    intent: GrooveIntent,
    bpm: float,
    candidate: int,
    tension: float,
    meter: MeterDefinition,
) -> GrooveEvent:
    dna = intent.target_dna
    rng = hrng.stream("event", candidate, instrument.value, bar, slot)
    structural = 0
    step_index = (grid_tick % meter.bar_ticks) // (PPQ // 4)
    if step_index % 2 == 1 and dna.swing > 0.01:
        tempo_attenuation = max(0.35, min(1.0, 150 / bpm))
        structural = int((PPQ // 4) * 0.32 * dna.swing * tempo_attenuation)
    contour = math.sin((bar + slot / 16) * math.pi / max(1, 4))
    pocket = INSTRUMENT_OFFSETS_US[instrument.value]
    noise = float(rng.normal(0, 900))
    micro = int((pocket + contour * 3_500 + noise) * dna.microtiming)
    micro = max(-MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, micro))
    gravity = metric_gravity(meter, grid_tick)
    base_velocity = {
        InstrumentID.KICK: 94,
        InstrumentID.SNARE: 96,
        InstrumentID.CLOSED_HAT: 72,
        InstrumentID.OPEN_HAT: 78,
        InstrumentID.PERCUSSION: 70,
        InstrumentID.BASS: 88,
    }[instrument]
    if role == EventRole.GHOST:
        velocity = int(25 + rng.random() * 20)
    else:
        contrast = dna.velocity_contrast * (gravity - 0.4) * 30
        velocity = int(base_velocity + contrast + tension * 7 + rng.normal(0, 2))
    velocity = max(1, min(127, velocity))
    duration_factor = 0.48 + dna.duration_contrast * float(rng.uniform(0.05, 1.1))
    if instrument == InstrumentID.BASS:
        duration_factor += 0.7
    duration = max(60, int((PPQ // 4) * duration_factor))
    pitch = 36 if instrument == InstrumentID.BASS else DRUM_PITCHES.get(instrument.value)
    choke = "hihat" if instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT) else None
    style = DurationStyle.STACCATO if duration < 180 else DurationStyle.MEDIUM
    tags = {EventRole.ANCHOR} if role in (EventRole.RECOVERY, EventRole.CONFIRMATION) else set()
    return GrooveEvent(
        event_id=hrng.id("event", candidate, instrument.value, bar, slot, grid_tick, role.value),
        instrument=instrument,
        grid_tick=grid_tick,
        structural_offset_tick=structural,
        micro_offset_us=micro,
        duration_tick=duration,
        velocity=velocity,
        pitch=pitch,
        primary_role=role,
        role_tags=tags,
        accent=max(0, min(1, accent)),
        duration_style=style,
        choke_group=choke,
    )


def generate_pattern(
    *,
    bpm: float,
    bars: int,
    meter: MeterDefinition,
    intent: GrooveIntent,
    seed: int,
    candidate: int = 0,
    name: str = "Generated Groove",
) -> GroovePattern:
    dna = intent.target_dna
    hrng = HierarchicalRNG(seed)
    phrase_rng = hrng.stream("phrase", candidate)
    grammar = choose_grammar(phrase_rng, dna.repetition, dna.variation)
    tensions = tension_curve(bars, dna.phrase_development, dna.hypnotic)
    step_tick = PPQ // 4
    strong = strong_positions(meter)
    events: list[GrooveEvent] = []

    for bar in range(bars):
        bar_start = bar * meter.bar_ticks
        steps = meter.bar_ticks // step_tick
        motif = motif_for_bar(grammar, bar)
        variation_scale = dna.variation * (0.25 if motif.startswith("A") else 0.8)
        tension = tensions[bar]
        for instrument in InstrumentID:
            rng = hrng.stream("instrument", candidate, instrument.value, bar)
            for slot in range(steps):
                tick = bar_start + slot * step_tick
                local = slot * step_tick
                gravity = metric_gravity(meter, local)
                on = False
                role = EventRole.DECORATION
                accent = gravity

                if instrument == InstrumentID.CLOSED_HAT:
                    stride = 1 if dna.density > 0.45 else 2
                    on = slot % stride == 0
                    if on:
                        role = EventRole.ANCHOR if slot % 4 == 0 else EventRole.CONFIRMATION
                        accent = 0.45 + 0.35 * gravity
                elif instrument == InstrumentID.KICK:
                    anchor_chance = 0.28 + dna.low_end_anchor * 0.3 + dna.pulse_stability * 0.38
                    on = local in strong and (local == 0 or rng.random() < anchor_chance)
                    if on:
                        role, accent = EventRole.ANCHOR, 0.82 + 0.16 * gravity
                    weak_chance = 0.04 + 0.35 * dna.syncopation + 0.12 * variation_scale
                    if not on and gravity < 0.5 and rng.random() < weak_chance / max(2, steps / 4):
                        on, role, accent = True, EventRole.VIOLATION, 0.55 + 0.25 * dna.syncopation
                elif instrument == InstrumentID.SNARE:
                    if meter.denominator == 8:
                        targets = strong[1::2] or strong[-1:]
                    else:
                        targets = [PPQ] if meter.numerator == 3 else [PPQ, 3 * PPQ]
                    on = local in targets
                    if on:
                        role, accent = EventRole.ANCHOR, 0.9
                    ghost_chance = dna.ghost_density * 0.18
                    if not on and gravity < 0.5 and rng.random() < ghost_chance / 2:
                        on, role, accent = True, EventRole.GHOST, 0.2
                elif instrument == InstrumentID.BASS:
                    kick_here = any(
                        e.instrument == InstrumentID.KICK and e.grid_tick == tick for e in events
                    )
                    lock_probability = 0.25 + 0.7 * dna.interlock
                    on = kick_here and rng.random() < lock_probability
                    if (
                        not on
                        and gravity < 0.5
                        and rng.random() < dna.syncopation * (1 - dna.interlock * 0.35) / 8
                    ):
                        on, role, accent = True, EventRole.ANTICIPATION, 0.65
                    elif on:
                        role, accent = EventRole.CONFIRMATION, 0.8
                elif instrument == InstrumentID.PERCUSSION:
                    occupied = any(
                        e.grid_tick == tick
                        and e.instrument in (InstrumentID.KICK, InstrumentID.SNARE)
                        for e in events
                    )
                    chance = dna.density * (0.12 + 0.22 * dna.interlock) / 4
                    on = (
                        (not occupied or dna.interlock < 0.3)
                        and gravity < 0.7
                        and rng.random() < chance
                    )
                    if on:
                        role, accent = EventRole.DECORATION, 0.45 + tension * 0.2
                elif instrument == InstrumentID.OPEN_HAT:
                    on = slot == steps - 2 and rng.random() < 0.12 + dna.variation * 0.25
                    if on:
                        role, accent = EventRole.TRANSITION, 0.65

                # Controlled omission preserves the first pulse carrier and phrase-ending recovery.
                if (
                    on
                    and role == EventRole.ANCHOR
                    and local != 0
                    and instrument == InstrumentID.KICK
                ):
                    omit = dna.omission * dna.surprise * (1 - dna.pulse_stability) * 0.35
                    on = rng.random() >= omit
                if (
                    bar == bars - 1
                    and local == strong[-1]
                    and instrument == InstrumentID.KICK
                    and dna.recovery_strength > 0.45
                ):
                    on, role, accent = True, EventRole.RECOVERY, 0.94
                if on:
                    events.append(
                        _event(
                            hrng,
                            instrument,
                            bar,
                            slot,
                            tick,
                            role,
                            accent,
                            intent,
                            bpm,
                            candidate,
                            tension,
                            meter,
                        )
                    )

    events.sort(key=lambda e: (e.grid_tick, e.instrument.value, e.event_id))
    return GroovePattern(
        pattern_id=f"pattern-{seed}-{candidate}",
        name=name,
        bpm=bpm,
        bars=bars,
        meter=meter,
        events=events,
        intent=intent,
        metadata=PatternMetadata(master_seed=seed),
    )
