from __future__ import annotations

import math

from app.config import DRUM_PITCHES, MAX_MICROTIMING_US, PPQ
from app.models.event import DurationStyle, EventRole, GrooveEvent, InstrumentID
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.models.pattern import GroovePattern, PatternMetadata
from app.random.seeds import HierarchicalRNG

from .embodied_operators import apply_embodied_operators
from .performance import PerformanceModel, load_performance_model, performance_adjustment
from .phrase import choose_grammar, motif_for_bar, tension_curve
from .pocket import pocket_for
from .pulse import metric_gravity, strong_positions
from .rhythm_language import phrase_rhythm_figure
from .style_language import (
    style_drum_variants,
    style_hat_profile,
    style_hat_variants,
    style_knowledge_pack,
    style_phrase_arrangements,
    style_rhythm_profile,
)


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
    style: str,
    bars: int,
    performance_model: PerformanceModel | None,
) -> GrooveEvent:
    dna = intent.target_dna
    rng = hrng.stream("event", candidate, instrument.value, bar, slot)
    structural = 0
    local_tick = grid_tick % meter.bar_ticks
    is_triplet_grid = meter.subdivisions_per_quarter in (3, 6)
    is_binary_off_sixteenth = local_tick % (PPQ // 2) == PPQ // 4
    if not is_triplet_grid and is_binary_off_sixteenth and dna.swing > 0.01:
        tempo_attenuation = max(0.35, min(1.0, 150 / bpm))
        structural = int((PPQ // 4) * 0.32 * dna.swing * tempo_attenuation)
    slots_per_four_beats = max(1, meter.subdivisions_per_quarter * 4)
    contour = math.sin((bar + slot / slots_per_four_beats) * math.pi / max(1, 4))
    profile = pocket_for(style)
    pocket = profile.offsets_us[instrument.value]
    noise = float(rng.normal(0, profile.jitter_us))
    rule_timing = pocket + contour * profile.phrase_contour_us + noise
    learned = None
    if performance_model is not None:
        learned = performance_adjustment(
            performance_model,
            hrng=hrng,
            style=style,
            bpm=bpm,
            instrument=instrument,
            bar=bar,
            bars=bars,
            slot=slot,
            subdivisions_per_quarter=meter.subdivisions_per_quarter,
            candidate=candidate,
        )
    expressive_timing = (
        rule_timing if learned is None else 0.25 * rule_timing + 0.75 * learned.timing_us
    )
    micro = int(expressive_timing * dna.microtiming)
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
        if learned is not None:
            learned_blend = 0.3 + 0.35 * dna.velocity_contrast
            velocity = round(
                (1 - learned_blend) * velocity + learned_blend * learned.target_velocity
            )
    if instrument == InstrumentID.CLOSED_HAT:
        # The hat is the most continuous voice, so its accent contour needs to
        # remain audible even when the learned performance layer is active.
        velocity += round((accent - 0.48) * 26)
        if role == EventRole.GHOST:
            velocity -= 8
    elif instrument == InstrumentID.OPEN_HAT:
        velocity += round((accent - 0.5) * 18)
    velocity = max(1, min(127, velocity))
    duration_factor = 0.48 + dna.duration_contrast * float(rng.uniform(0.05, 1.1))
    if instrument == InstrumentID.BASS:
        duration_factor += 0.7
    elif instrument == InstrumentID.CLOSED_HAT:
        duration_factor = 0.23 + 0.22 * dna.duration_contrast
    elif instrument == InstrumentID.OPEN_HAT:
        duration_factor = 0.9 + 0.48 * dna.duration_contrast
    duration = max(60, int((PPQ // 4) * duration_factor))
    pitch = 36 if instrument == InstrumentID.BASS else DRUM_PITCHES.get(instrument.value)
    choke = "hihat" if instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT) else None
    duration_style = DurationStyle.STACCATO if duration < 180 else DurationStyle.MEDIUM
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
        duration_style=duration_style,
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
    style: str = "Balanced",
    performance_mode: str = "auto",
    render_profile: str = "studio-tight-v1",
) -> GroovePattern:
    dna = intent.target_dna
    hrng = HierarchicalRNG(seed)
    performance_model = None if performance_mode == "rule" else load_performance_model()
    phrase_rng = hrng.stream("phrase", candidate)
    # Hypnotic intent reinforces motif identity, while a deliberately low value
    # opens space for a more narrative phrase.  Folding that intent into the
    # grammar keeps the control structural instead of merely changing accents.
    phrase_repetition = max(0.0, min(1.0, dna.repetition + 0.35 * (dna.hypnotic - 0.5)))
    phrase_variation = max(0.0, min(1.0, dna.variation + 0.25 * (0.5 - dna.hypnotic)))
    grammar = choose_grammar(phrase_rng, phrase_repetition, phrase_variation)
    tensions = tension_curve(bars, dna.phrase_development, dna.hypnotic, intent.phrase_energy_curve)
    step_tick = meter.subdivision_tick
    triplet_grid = meter.subdivisions_per_quarter in (3, 6)
    carrier_subdivisions = 3 if triplet_grid else min(4, meter.subdivisions_per_quarter)
    carrier_tick = PPQ // carrier_subdivisions
    strong = strong_positions(meter)
    style_rhythm = style_rhythm_profile(style, meter)
    hat_style = style_hat_profile(style, meter)
    hat_variants = style_hat_variants(style, meter)
    drum_variants = style_drum_variants(style, meter)
    phrase_arrangements = style_phrase_arrangements(style, meter)
    events: list[GrooveEvent] = []
    hat_variant_ids: list[str] = []
    drum_variant_ids: list[str] = []
    phrase_arrangement_ids: list[str] = []

    for bar in range(bars):
        bar_start = bar * meter.bar_ticks
        steps = meter.bar_ticks // step_tick
        motif = motif_for_bar(grammar, bar)
        rhythm_figure = phrase_rhythm_figure(meter, motif)
        arrangement_rng = hrng.stream("phrase-arrangement", candidate, bar // 4, grammar)
        arrangement = phrase_arrangements[int(arrangement_rng.integers(len(phrase_arrangements)))]
        arrangement_slot = bar % len(arrangement.vocabulary_offsets)
        vocabulary_rng = hrng.stream("kit-vocabulary", candidate, bar // 2, motif)
        vocabulary_index = (
            int(vocabulary_rng.integers(len(hat_variants)))
            + arrangement.vocabulary_offsets[arrangement_slot]
        ) % len(hat_variants)
        hat_variant = hat_variants[vocabulary_index]
        drum_variant = drum_variants[vocabulary_index % len(drum_variants)]
        hat_variant_ids.append(hat_variant.variant_id)
        drum_variant_ids.append(drum_variant.variant_id)
        phrase_arrangement_ids.append(arrangement.arrangement_id)
        variation_scale = dna.variation * (0.25 if motif.startswith("A") else 0.8)
        tension = min(1.0, tensions[bar] * arrangement.tension_scales[arrangement_slot])
        for instrument in InstrumentID:
            rng = hrng.stream("instrument", candidate, instrument.value, bar)
            stable_rng = hrng.stream("instrument-stable", candidate, instrument.value)
            motor_energy = dna.motor_affordance
            structural_randomness = min(
                1.0,
                max(
                    0.0,
                    variation_scale
                    + (1 - dna.pulse_stability) * 0.35
                    + dna.metric_ambiguity * 0.15
                    + motor_energy * 0.22
                    + (0.5 - dna.repetition) * 0.38
                    + (0.5 - dna.hypnotic) * 0.52,
                ),
            )

            def structural_draw() -> float:
                return float(
                    (1 - structural_randomness) * stable_rng.random()
                    + structural_randomness * rng.random()
                )

            for slot in range(steps):
                tick = bar_start + slot * step_tick
                local = slot * step_tick
                gravity = metric_gravity(meter, local)
                on = False
                role = EventRole.DECORATION
                accent = gravity

                if instrument == InstrumentID.CLOSED_HAT:
                    # A hi-hat is not generated as an isolated metronome.  It
                    # carries a slower spine, fills selected subdivisions, then
                    # responds to the kick/snare conversation and phrase state.
                    # Kick and snare have already been generated for this bar.
                    kick_here = any(
                        event.instrument == InstrumentID.KICK and event.grid_tick == tick
                        for event in events
                    )
                    snare_here = any(
                        event.instrument == InstrumentID.SNARE and event.grid_tick == tick
                        for event in events
                    )
                    previous_kick = any(
                        event.instrument == InstrumentID.KICK
                        and event.grid_tick == tick - step_tick
                        for event in events
                    )
                    next_snare = any(
                        event.instrument == InstrumentID.SNARE
                        and event.grid_tick == tick + step_tick
                        for event in events
                    )
                    spine_tick = PPQ // (3 if triplet_grid else 2)
                    eighth_index = local // (PPQ // 2) if local % (PPQ // 2) == 0 else None
                    sixteenth_index = local // (PPQ // 4) if local % (PPQ // 4) == 0 else None
                    if hat_style.spine == "sixteenth":
                        spine = local % carrier_tick == 0
                    elif hat_style.spine == "offbeat":
                        spine = local % PPQ == PPQ // 2
                    else:
                        spine = local % spine_tick == 0
                    subdivision = local % carrier_tick == 0
                    phrase_end_window = slot >= steps - min(4, carrier_subdivisions)
                    spine_chance = min(
                        0.98,
                        0.25
                        + 0.55 * hat_style.spine_probability
                        + 0.13 * dna.pulse_stability
                        + 0.11 * dna.motor_affordance
                        + 0.08 * dna.density
                        + 0.06 * dna.beat_salience,
                    )
                    on = spine and (
                        local == 0
                        or hat_style.spine == "offbeat"
                        or structural_draw() < spine_chance
                    )
                    if on:
                        role = EventRole.ANCHOR if local % PPQ == 0 else EventRole.CONFIRMATION
                        accent = 0.46 + 0.42 * gravity

                    # Pushes after kick hits, pickups into the snare and the
                    # shared phrase-answer position create interlocking motion.
                    response_chance = (
                        0.12
                        + 0.38 * dna.interlock
                        + 0.28 * dna.syncopation
                        + 0.18 * dna.motor_affordance
                        + 0.22 * hat_style.pickup_bias
                    ) * (0.72 + 0.35 * tension) * hat_variant.pickup_scale
                    if (
                        not on
                        and previous_kick
                        and gravity < 0.72
                        and structural_draw() < response_chance
                    ):
                        on, role, accent = True, EventRole.CONFIRMATION, 0.42 + 0.26 * dna.interlock
                    if (
                        not on
                        and next_snare
                        and gravity < 0.72
                        and structural_draw() < response_chance * 0.82
                    ):
                        on, role, accent = (
                            True,
                            EventRole.ANTICIPATION,
                            0.38 + 0.28 * dna.anticipation,
                        )
                    if not on and local == rhythm_figure.answer_tick:
                        answer_chance = max(0, dna.syncopation - 0.12) * (
                            0.28 + 0.44 * dna.motor_affordance + 0.24 * tension
                        )
                        if structural_draw() < answer_chance:
                            on, role, accent = (
                                True,
                                EventRole.CONFIRMATION,
                                0.48 + 0.2 * dna.syncopation,
                            )

                    # A deliberate pickup before a tactus can replace the
                    # following closed-hat stroke.  This creates actual
                    # syncopation (weak attack → expected strong-space), not
                    # merely more notes between the beats.
                    pre_tactus = local % PPQ == PPQ - step_tick
                    if not on and pre_tactus and local + step_tick < meter.bar_ticks:
                        pickup_chance = (
                            0.04
                            + 0.52 * dna.syncopation
                            + 0.16 * dna.anticipation
                            + 0.12 * dna.interlock
                        ) * (0.6 + 0.4 * tension)
                        if structural_draw() < pickup_chance:
                            on, role, accent = (
                                True,
                                EventRole.ANTICIPATION,
                                0.42 + 0.3 * dna.syncopation,
                            )

                    # The phrase ending can briefly become more detailed, but
                    # only on legal inner subdivisions and never on every bar.
                    subdivision_chance = (
                        max(0, dna.density - 0.34) * 0.34
                        + variation_scale * 0.22
                        + dna.surprise * 0.12
                        + dna.metric_ambiguity * 0.11
                        + 0.22 * hat_style.subdivision_bias
                    ) * (0.62 + 0.48 * tension) * hat_variant.subdivision_scale
                    if (
                        not on
                        and subdivision
                        and not kick_here
                        and structural_draw() < subdivision_chance
                    ):
                        on, role, accent = True, EventRole.DECORATION, 0.26 + 0.2 * tension
                    if (
                        not on
                        and phrase_end_window
                        and motif != "A"
                        and gravity < 0.7
                    ):
                        if structural_draw() < subdivision_chance * 0.9:
                            on, role, accent = True, EventRole.TRANSITION, 0.34 + 0.22 * tension
                    if not on and local in style_rhythm.reinforced_hat_ticks:
                        on = structural_draw() < style_rhythm.hat_probability
                        if on:
                            role, accent = EventRole.CONFIRMATION, 0.44 + 0.28 * gravity

                    # Vocabulary-level variation happens after the shared
                    # skeleton: it can leave a deliberate rest, add a legal
                    # 16th answer or move the accent contour without changing
                    # the meter or the selected style's core role.
                    if (
                        on
                        and eighth_index in hat_variant.omit_eighths
                        and role != EventRole.ANCHOR
                    ):
                        on = False
                    if (
                        not on
                        and sixteenth_index in hat_variant.add_sixteenths
                        and not kick_here
                        and structural_draw() < 0.5 + 0.35 * dna.density
                    ):
                        on, role, accent = True, EventRole.DECORATION, 0.3 + 0.18 * tension
                    if on and eighth_index in hat_variant.accent_eighths:
                        accent = min(1.0, accent + 0.18 + 0.16 * dna.velocity_contrast)

                    # A small amount of space around some backbeats prevents a
                    # continuous grid from masking the snare's answer.
                    if on and snare_here and local != 0:
                        breathing_room = (
                            0.06 + 0.18 * dna.variation + 0.18 * hat_style.backbeat_space
                        ) * (1 - 0.5 * dna.density)
                        if role == EventRole.CONFIRMATION and structural_draw() < breathing_room:
                            on = False
                    if (
                        on
                        and (kick_here or snare_here)
                        and local != 0
                        and hat_style.linear_bias > 0
                        and role != EventRole.ANCHOR
                    ):
                        linear_space = (
                            0.03 + 0.26 * hat_style.linear_bias * (0.45 + 0.55 * variation_scale)
                        )
                        if structural_draw() < linear_space:
                            on = False
                    preceding_pickup = next(
                        (
                            event
                            for event in events
                            if event.instrument == InstrumentID.CLOSED_HAT
                            and event.grid_tick == tick - step_tick
                        ),
                        None,
                    )
                    if (
                        on
                        and local % PPQ == 0
                        and local != 0
                        and preceding_pickup is not None
                        and preceding_pickup.primary_role == EventRole.ANTICIPATION
                    ):
                        release_chance = (
                            0.08 + 0.62 * dna.syncopation + 0.14 * hat_style.linear_bias
                        )
                        if structural_draw() < release_chance:
                            on = False
                elif instrument == InstrumentID.KICK:
                    sixteenth_index = local // (PPQ // 4) if local % (PPQ // 4) == 0 else None
                    anchor_chance = max(
                        0.08,
                        min(
                            0.98,
                            0.02
                            + dna.low_end_anchor * 0.46
                            + dna.pulse_stability * 0.24
                            + dna.beat_salience * 0.65
                            - 0.2925
                            + dna.motor_affordance * 0.1
                            - dna.metric_ambiguity * 0.28,
                        ),
                    )
                    on = local in strong and (local == 0 or structural_draw() < anchor_chance)
                    if on:
                        role, accent = EventRole.ANCHOR, 0.82 + 0.16 * gravity
                    weak_chance = (
                        0.02
                        + 0.3 * dna.syncopation
                        + 0.16 * variation_scale
                        + 0.3 * dna.surprise
                        + 0.26 * dna.metric_ambiguity
                        + 0.58 * motor_energy
                    ) * (0.75 + 0.5 * tension)
                    weak_chance *= (
                        (1.08 - 0.5 * dna.hypnotic)
                        * (1.12 - 0.3 * dna.low_end_anchor)
                        * drum_variant.kick_weak_scale
                    )
                    if (
                        not on
                        and gravity < 0.5
                        and structural_draw() < weak_chance / max(2, steps / 4)
                    ):
                        on, role, accent = True, EventRole.VIOLATION, 0.55 + 0.25 * dna.syncopation
                    if not on and local == rhythm_figure.call_tick:
                        call_chance = (
                            max(0, dna.syncopation - 0.2)
                            * (0.18 + 0.42 * dna.motor_affordance + 0.14 * dna.surprise)
                            * (0.75 + 0.25 * tension)
                        )
                        if structural_draw() < call_chance:
                            on, role, accent = (
                                True,
                                EventRole.VIOLATION,
                                0.52 + 0.3 * dna.syncopation,
                            )
                    if (
                        not on
                        and sixteenth_index in drum_variant.kick_add_sixteenths
                        and gravity < 0.72
                        and structural_draw() < 0.48 + 0.32 * dna.density
                    ):
                        on, role, accent = (
                            True,
                            EventRole.CONFIRMATION,
                            0.48 + 0.22 * dna.low_end_anchor,
                        )
                elif instrument == InstrumentID.SNARE:
                    if meter.denominator == 8:
                        targets = strong[1::2] or strong[-1:]
                    else:
                        targets = [PPQ] if meter.numerator == 3 else [PPQ, 3 * PPQ]
                    on = local in targets
                    if on:
                        role, accent = EventRole.ANCHOR, 0.9
                    sixteenth_index = local // (PPQ // 4) if local % (PPQ // 4) == 0 else None
                    kick_here = any(
                        event.instrument == InstrumentID.KICK and event.grid_tick == tick
                        for event in events
                    )
                    ghost_chance = dna.ghost_density * 0.18 * drum_variant.snare_ghost_scale
                    if not on and gravity < 0.5 and structural_draw() < ghost_chance / 2:
                        on, role, accent = True, EventRole.GHOST, 0.2
                    if (
                        not on
                        and not kick_here
                        and sixteenth_index in drum_variant.snare_ghost_sixteenths
                        and structural_draw() < 0.34 + 0.34 * dna.ghost_density
                    ):
                        on, role, accent = True, EventRole.GHOST, 0.24 + 0.14 * tension
                    if (
                        not on
                        and not kick_here
                        and sixteenth_index in drum_variant.snare_transition_sixteenths
                        and structural_draw() < 0.4 + 0.28 * tension
                    ):
                        on, role, accent = True, EventRole.TRANSITION, 0.36 + 0.2 * tension
                elif instrument == InstrumentID.BASS:
                    kick_here = any(
                        e.instrument == InstrumentID.KICK and e.grid_tick == tick for e in events
                    )
                    lock_probability = min(
                        0.98,
                        0.18
                        + 0.52 * dna.interlock
                        + 0.32 * dna.low_end_anchor
                        + 0.16 * (dna.beat_salience - 0.75),
                    )
                    on = kick_here and structural_draw() < lock_probability
                    if (
                        not on
                        and gravity < 0.5
                        and structural_draw()
                        < dna.syncopation
                        * (0.03 + 0.17 * dna.anticipation)
                        * (1 - dna.interlock * 0.35)
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
                    chance = (
                        dna.density * (0.16 + 0.26 * dna.interlock) / 3 * (0.55 + 0.9 * tension)
                        + dna.metric_ambiguity * 0.045
                        + dna.surprise * 0.035
                        + motor_energy * 0.12
                    )
                    chance *= 1.08 - 0.4 * dna.hypnotic
                    on = (
                        (not occupied or dna.interlock < 0.3)
                        and gravity < 0.7
                        and structural_draw() < chance
                    )
                    if not on and local == rhythm_figure.turnaround_tick:
                        turnaround_chance = (
                            max(0, dna.variation - 0.25)
                            * (0.08 + 0.2 * dna.interlock + 0.16 * dna.surprise)
                            * tension
                        )
                        on = structural_draw() < turnaround_chance
                    if on:
                        role, accent = EventRole.DECORATION, 0.45 + tension * 0.2
                elif instrument == InstrumentID.OPEN_HAT:
                    closed_here = any(
                        event.instrument == InstrumentID.CLOSED_HAT and event.grid_tick == tick
                        for event in events
                    )
                    next_local = local + step_tick
                    spine_tick = PPQ // (3 if triplet_grid else 2)
                    lead_into_spine = (
                        next_local < meter.bar_ticks and next_local % spine_tick == 0
                    )
                    lead_into_snare = any(
                        event.instrument == InstrumentID.SNARE
                        and event.grid_tick == tick + step_tick
                        for event in events
                    )
                    phrase_exit = slot >= steps - min(3, carrier_subdivisions)
                    open_chance = (
                        0.03
                        + 0.22 * dna.variation
                        + 0.16 * dna.surprise
                        + 0.18 * dna.motor_affordance
                        + 0.24 * dna.interlock
                        + 0.12 * tension
                        + 0.42 * hat_style.open_bias
                    ) * (1.08 - 0.45 * dna.hypnotic) * hat_variant.open_scale
                    eighth_index = local // (PPQ // 2) if local % (PPQ // 2) == 0 else None
                    if eighth_index in hat_variant.open_eighths:
                        open_chance *= 1.65
                    two_bar_lift = (
                        hat_style.two_bar_variation
                        and bar % 2 == 1
                        and phrase_exit
                    )
                    open_can_replace_closed = (
                        hat_style.open_replaces_closed
                        or (
                            hat_style.open_bias >= 0.45
                            and (phrase_exit or local == rhythm_figure.turnaround_tick)
                        )
                    )
                    on = (
                        (not closed_here or open_can_replace_closed)
                        and (lead_into_spine or lead_into_snare or phrase_exit)
                        and structural_draw() < open_chance * (1.25 if two_bar_lift else 1.0)
                    )
                    if (
                        not on
                        and (not closed_here or open_can_replace_closed)
                        and local == rhythm_figure.turnaround_tick
                    ):
                        on = structural_draw() < open_chance * (0.65 + 0.35 * tension)
                    if on:
                        if closed_here:
                            events[:] = [
                                event
                                for event in events
                                if not (
                                    event.instrument == InstrumentID.CLOSED_HAT
                                    and event.grid_tick == tick
                                )
                            ]
                        role = EventRole.ANTICIPATION if lead_into_snare else EventRole.TRANSITION
                        accent = 0.52 + 0.24 * tension

                # Controlled omission preserves the first pulse carrier and phrase-ending recovery.
                if (
                    on
                    and role == EventRole.ANCHOR
                    and local != 0
                    and instrument == InstrumentID.KICK
                ):
                    omit = (
                        dna.omission
                        * (0.25 + 0.75 * dna.surprise)
                        * (0.35 + 0.65 * (1 - dna.pulse_stability))
                        * 0.65
                    )
                    on = structural_draw() >= omit
                if instrument == InstrumentID.KICK and local in style_rhythm.forced_kick_ticks:
                    on, role, accent = True, EventRole.ANCHOR, 0.82 + 0.16 * gravity
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
                            style,
                            bars,
                            performance_model,
                        )
                    )

    events.sort(key=lambda e: (e.grid_tick, e.instrument.value, e.event_id))
    pack = style_knowledge_pack(style, meter)
    pattern = GroovePattern(
        pattern_id=f"pattern-{seed}-{candidate}",
        name=name,
        bpm=bpm,
        bars=bars,
        meter=meter,
        events=events,
        intent=intent,
        metadata=PatternMetadata(
            master_seed=seed,
            style=style,
            performance_model=(
                performance_model.model_id if performance_model is not None else "rule-pocket-v1"
            ),
            performance_model_version=(
                performance_model.model_version if performance_model is not None else "1.0.0"
            ),
            render_profile=render_profile,
            knowledge_pack_id=pack.pack_id,
            knowledge_pack_version=pack.version,
            hat_language_profile=hat_style.profile_id,
            hat_variant_ids=hat_variant_ids,
            drum_variant_ids=drum_variant_ids,
            phrase_arrangement_ids=phrase_arrangement_ids,
        ),
    )
    pattern.metadata.embodied_operator_arm = apply_embodied_operators(pattern)
    return pattern
