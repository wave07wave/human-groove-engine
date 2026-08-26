from __future__ import annotations

from app.config import PPQ
from app.engine.pulse import metric_gravity

from .harmony import harmony_at
from .models import BassDecisionTrace, BassEvent, BassPattern

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
PHRASE_PHASES = ("anchor", "development", "tension", "recovery")


def midi_note_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def _kick_relationship(pattern: BassPattern, tick: int) -> str:
    context = pattern.groove_context
    if not context or not context.kick_events:
        return "independent"
    kicks = [event.performed_tick for event in context.kick_events]
    if any(abs(tick - kick) <= 80 for kick in kicks):
        return "lock"
    if any(0 < kick - tick <= PPQ // 4 for kick in kicks):
        return "anticipate"
    if any(0 < tick - kick <= PPQ // 2 for kick in kicks):
        return "answer"
    return "complement"


def _harmony_name(pattern: BassPattern, event: BassEvent) -> str:
    harmony = harmony_at(pattern.harmony, event.grid_tick)
    if not harmony.chord:
        return "the active key/scale"
    root = harmony.chord.root
    accidental = "#" * max(0, root.accidental) + "b" * max(0, -root.accidental)
    return f"{root.letter}{accidental} {harmony.chord.quality.value}"


def decision_trace(pattern: BassPattern, event: BassEvent) -> BassDecisionTrace:
    gravity = metric_gravity(pattern.meter, event.grid_tick)
    bar = event.grid_tick // pattern.meter.bar_ticks
    phase = PHRASE_PHASES[bar % 4]
    relation = _kick_relationship(pattern, event.performed_tick)
    center_distance = event.pitch - pattern.register_limits.preferred_center
    register_direction = (
        "at" if not center_distance else "above" if center_distance > 0 else "below"
    )
    target = next(
        (item for item in pattern.events if item.event_id == event.approach_target_id), None
    )
    mutation = event.provenance.mutation_operation
    prefix = f"After {mutation.replace('_', ' ')} regeneration, " if mutation else ""
    onset = (
        f"{prefix}bar {bar + 1} uses the {phase} phrase phase; "
        f"{event.rhythmic_role.value.replace('_', ' ')} was retained at metric gravity "
        f"{gravity:.2f}; Kick relationship: {relation}."
    )
    pitch = (
        f"{midi_note_name(event.pitch)} functions as {event.harmonic_role.value.replace('_', ' ')} "
        f"against {_harmony_name(pattern, event)}."
    )
    if target:
        direction = "upward" if target.pitch > event.pitch else "downward"
        pitch += (
            f" It approaches {midi_note_name(target.pitch)} {direction} by "
            f"{abs(target.pitch - event.pitch)} semitone(s)."
        )
    duration = (
        f"{event.duration_tick} ticks ({event.duration_tick / PPQ:.2f} quarter notes) supports "
        f"a {event.articulation.connection.value} connection and preserves the following space."
    )
    octave = (
        f"{midi_note_name(event.pitch)} sits {abs(center_distance):.1f} semitone(s) "
        f"{register_direction} "
        f"the preferred center MIDI {pattern.register_limits.preferred_center:g}, inside "
        f"{pattern.register_limits.lowest_midi_note}–{pattern.register_limits.highest_midi_note}."
    )
    articulation = (
        f"{event.articulation.connection.value}, {event.articulation.technique.value}, "
        f"{event.articulation.accent.value}; velocity {event.velocity} and "
        f"microtiming {event.micro_offset_us / 1000:+.1f} ms follow structural weight "
        f"{event.structural_weight:.2f}."
    )
    return BassDecisionTrace(
        onset_reason=onset,
        pitch_reason=pitch,
        duration_reason=duration,
        octave_reason=octave,
        articulation_reason=articulation,
        kick_relationship=relation,
        target_event_id=target.event_id if target else None,
        target_pitch=target.pitch if target else None,
        factors={
            "metric_gravity": gravity,
            "structural_weight": event.structural_weight,
            "register_distance": abs(center_distance)
            / max(
                1,
                pattern.register_limits.highest_midi_note
                - pattern.register_limits.lowest_midi_note,
            ),
            "human_feel": pattern.intent.target.human_feel,
            "duration_contrast": pattern.intent.target.duration_contrast,
            "kick_lock_target": pattern.intent.target.kick_lock,
        },
    )


def attach_decision_traces(pattern: BassPattern) -> BassPattern:
    for event in pattern.events:
        event.decision_trace = decision_trace(pattern, event)
    return pattern
