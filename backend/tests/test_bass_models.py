from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.bass.generation import generate_bass_pattern
from app.bass.harmony import build_harmony_timeline, parse_chord, parse_pitch_class
from app.bass.models import (
    BassEvent,
    BassGenerateRequest,
    BassPattern,
    BassStructuralEvent,
    HarmonicRole,
    InputMode,
    RhythmicRole,
    ScaleMode,
    StructuralRole,
)
from app.models.meter import MeterDefinition


def test_pitch_spelling_preserves_enharmonic_identity() -> None:
    sharp = parse_pitch_class("C#")
    flat = parse_pitch_class("Db")
    assert sharp.pitch_class == flat.pitch_class == 1
    assert (sharp.letter, sharp.accidental) != (flat.letter, flat.accidental)


@pytest.mark.parametrize(
    ("symbol", "quality", "root", "bass"),
    [
        ("Cmaj7", "major7", 0, None),
        ("Dm7", "minor7", 2, None),
        ("G7", "dominant7", 7, None),
        ("F#m7b5", "minor7b5", 6, None),
        ("Cmaj7/E", "major7", 0, 4),
    ],
)
def test_chord_parser(symbol: str, quality: str, root: int, bass: int | None) -> None:
    chord = parse_chord(symbol)
    assert chord is not None
    assert chord.quality.value == quality
    assert chord.root.pitch_class == root
    assert (chord.bass_note.pitch_class if chord.bass_note else None) == bass


def test_harmony_timeline_cycles_independently_of_output_length() -> None:
    meter = MeterDefinition.from_name("4/4")
    timeline, _ = build_harmony_timeline(
        harmony="Dm7 | G7",
        bars=16,
        meter=meter,
        input_mode=InputMode.CHORD_PROGRESSION,
        key="C",
        mode=ScaleMode.MAJOR,
    )
    assert len(timeline.events) == 16
    assert timeline.events[0].chord.root.pitch_class == timeline.events[2].chord.root.pitch_class
    assert timeline.events[1].chord.root.pitch_class == timeline.events[3].chord.root.pitch_class


def test_no_chord_is_explicit() -> None:
    meter = MeterDefinition.from_name("4/4")
    timeline, context = build_harmony_timeline(
        harmony="ignored",
        bars=4,
        meter=meter,
        input_mode=InputMode.NO_HARMONY,
        key="D",
        mode=ScaleMode.DORIAN,
    )
    assert context is not None
    assert all(event.chord is None for event in timeline.events)


def test_approach_event_requires_valid_target_field() -> None:
    with pytest.raises(ValidationError):
        BassEvent(
            event_id="approach",
            grid_tick=0,
            duration_tick=120,
            pitch=47,
            velocity=80,
            harmonic_role=HarmonicRole.CHROMATIC_APPROACH,
            rhythmic_role=RhythmicRole.ANTICIPATION,
            phrase_id="p0",
        )


def test_pattern_rejects_out_of_range_duration_and_structural_target() -> None:
    pattern = generate_bass_pattern(BassGenerateRequest(bars=2), candidate=0)
    end_tick = pattern.bars * pattern.meter.bar_ticks
    payload = pattern.model_dump()
    payload["events"][-1]["duration_tick"] = end_tick
    with pytest.raises(ValidationError, match="duration exceeds pattern"):
        BassPattern.model_validate(payload)

    payload = pattern.model_dump()
    payload["structural_events"] = [
        BassStructuralEvent(
            event_id="bad-target",
            start_tick=0,
            duration_tick=120,
            role=StructuralRole.RECOVERY_TARGET,
            target_event_id="missing",
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="structural target"):
        BassPattern.model_validate(payload)
