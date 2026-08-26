from __future__ import annotations

import re

from app.models.meter import MeterDefinition

from .models import (
    Chord,
    ChordQuality,
    HarmonicRole,
    HarmonyEvent,
    HarmonyTimeline,
    InputMode,
    KeyContext,
    ScaleMode,
    SpelledPitchClass,
)

NATURAL_PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

QUALITY_INTERVALS: dict[ChordQuality, tuple[int, ...]] = {
    ChordQuality.MAJOR: (0, 4, 7),
    ChordQuality.MINOR: (0, 3, 7),
    ChordQuality.MAJOR7: (0, 4, 7, 11),
    ChordQuality.DOMINANT7: (0, 4, 7, 10),
    ChordQuality.MINOR7: (0, 3, 7, 10),
    ChordQuality.MINOR7B5: (0, 3, 6, 10),
    ChordQuality.DIM: (0, 3, 6),
    ChordQuality.DIM7: (0, 3, 6, 9),
    ChordQuality.AUG: (0, 4, 8),
    ChordQuality.SUS2: (0, 2, 7),
    ChordQuality.SUS4: (0, 5, 7),
    ChordQuality.SIX: (0, 4, 7, 9),
    ChordQuality.MINOR6: (0, 3, 7, 9),
    ChordQuality.ADD9: (0, 4, 7, 2),
    ChordQuality.NINE: (0, 4, 7, 10, 2),
    ChordQuality.ELEVEN: (0, 4, 7, 10, 2, 5),
    ChordQuality.THIRTEEN: (0, 4, 7, 10, 2, 5, 9),
}

MODE_INTERVALS: dict[ScaleMode, tuple[int, ...]] = {
    ScaleMode.MAJOR: (0, 2, 4, 5, 7, 9, 11),
    ScaleMode.NATURAL_MINOR: (0, 2, 3, 5, 7, 8, 10),
    ScaleMode.HARMONIC_MINOR: (0, 2, 3, 5, 7, 8, 11),
    ScaleMode.MELODIC_MINOR: (0, 2, 3, 5, 7, 9, 11),
    ScaleMode.DORIAN: (0, 2, 3, 5, 7, 9, 10),
    ScaleMode.PHRYGIAN: (0, 1, 3, 5, 7, 8, 10),
    ScaleMode.LYDIAN: (0, 2, 4, 6, 7, 9, 11),
    ScaleMode.MIXOLYDIAN: (0, 2, 4, 5, 7, 9, 10),
    ScaleMode.AEOLIAN: (0, 2, 3, 5, 7, 8, 10),
    ScaleMode.LOCRIAN: (0, 1, 3, 5, 6, 8, 10),
    ScaleMode.MAJOR_PENTATONIC: (0, 2, 4, 7, 9),
    ScaleMode.MINOR_PENTATONIC: (0, 3, 5, 7, 10),
    ScaleMode.BLUES: (0, 3, 5, 6, 7, 10),
    ScaleMode.CHROMATIC: tuple(range(12)),
}

_QUALITY_ALIASES = {
    "": ChordQuality.MAJOR,
    "maj": ChordQuality.MAJOR,
    "m": ChordQuality.MINOR,
    "min": ChordQuality.MINOR,
    "maj7": ChordQuality.MAJOR7,
    "M7": ChordQuality.MAJOR7,
    "7": ChordQuality.DOMINANT7,
    "m7": ChordQuality.MINOR7,
    "min7": ChordQuality.MINOR7,
    "m7b5": ChordQuality.MINOR7B5,
    "ø": ChordQuality.MINOR7B5,
    "dim": ChordQuality.DIM,
    "o": ChordQuality.DIM,
    "dim7": ChordQuality.DIM7,
    "o7": ChordQuality.DIM7,
    "aug": ChordQuality.AUG,
    "+": ChordQuality.AUG,
    "sus2": ChordQuality.SUS2,
    "sus4": ChordQuality.SUS4,
    "6": ChordQuality.SIX,
    "m6": ChordQuality.MINOR6,
    "add9": ChordQuality.ADD9,
    "9": ChordQuality.NINE,
    "11": ChordQuality.ELEVEN,
    "13": ChordQuality.THIRTEEN,
}


def parse_pitch_class(token: str) -> SpelledPitchClass:
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]{0,2})\s*", token)
    if not match:
        raise ValueError(f"invalid pitch spelling: {token}")
    letter = match.group(1).upper()
    symbols = match.group(2)
    accidental = symbols.count("#") - symbols.count("b")
    return SpelledPitchClass(
        letter=letter,
        accidental=accidental,
        pitch_class=(NATURAL_PITCH_CLASSES[letter] + accidental) % 12,
    )


def _spell_from_pc(pitch_class: int, prefer_flats: bool = False) -> SpelledPitchClass:
    sharps = (
        ("C", 0),
        ("C", 1),
        ("D", 0),
        ("D", 1),
        ("E", 0),
        ("F", 0),
        ("F", 1),
        ("G", 0),
        ("G", 1),
        ("A", 0),
        ("A", 1),
        ("B", 0),
    )
    flats = (
        ("C", 0),
        ("D", -1),
        ("D", 0),
        ("E", -1),
        ("E", 0),
        ("F", 0),
        ("G", -1),
        ("G", 0),
        ("A", -1),
        ("A", 0),
        ("B", -1),
        ("B", 0),
    )
    letter, accidental = (flats if prefer_flats else sharps)[pitch_class % 12]
    return SpelledPitchClass(letter=letter, accidental=accidental, pitch_class=pitch_class % 12)


def parse_chord(symbol: str) -> Chord | None:
    symbol = symbol.strip()
    if symbol.upper() in {"N.C.", "NC", "NO_CHORD", "-"}:
        return None
    match = re.fullmatch(r"([A-Ga-g](?:#|b){0,2})([^/]*)?(?:/([A-Ga-g](?:#|b){0,2}))?", symbol)
    if not match:
        raise ValueError(f"invalid chord symbol: {symbol}")
    root = parse_pitch_class(match.group(1))
    suffix = (match.group(2) or "").strip()
    quality = _QUALITY_ALIASES.get(suffix)
    if quality is None:
        raise ValueError(f"unsupported chord quality in: {symbol}")
    intervals = QUALITY_INTERVALS[quality]
    tones = [
        _spell_from_pc(root.pitch_class + interval, "b" in match.group(1)) for interval in intervals
    ]
    return Chord(
        root=root,
        quality=quality,
        spelled_tones=tones,
        pitch_classes={tone.pitch_class for tone in tones},
        extensions=[interval for interval in intervals if interval in (2, 5, 9)],
        bass_note=parse_pitch_class(match.group(3)) if match.group(3) else None,
    )


def key_context(key: str | None, mode: ScaleMode) -> KeyContext | None:
    return KeyContext(tonic=parse_pitch_class(key), mode=mode) if key else None


def build_harmony_timeline(
    *,
    harmony: str,
    bars: int,
    meter: MeterDefinition,
    input_mode: InputMode,
    key: str | None,
    mode: ScaleMode,
) -> tuple[HarmonyTimeline, KeyContext | None]:
    context = key_context(key, mode)
    raw = [part.strip() for part in harmony.split("|") if part.strip()]
    if input_mode == InputMode.NO_HARMONY:
        raw = ["NO_CHORD"]
    elif input_mode == InputMode.KEY_MODE:
        raw = ["NO_CHORD"]
    elif input_mode == InputMode.ROOT_GUIDE:
        raw = raw or ([key] if key else [])
    if not raw:
        raise ValueError("harmony input must contain at least one chord, root, or key")
    chords = [parse_chord(token) for token in raw]
    events = [
        HarmonyEvent(
            start_tick=bar * meter.bar_ticks,
            duration_tick=meter.bar_ticks,
            chord=chords[bar % len(chords)],
            key_context=context,
        )
        for bar in range(bars)
    ]
    return HarmonyTimeline(events=events), context


def harmony_at(timeline: HarmonyTimeline, tick: int) -> HarmonyEvent:
    for event in timeline.events:
        if event.start_tick <= tick < event.start_tick + event.duration_tick:
            return event
    return timeline.events[-1]


def scale_pitch_classes(context: KeyContext | None) -> set[int]:
    if context is None:
        return set(range(12))
    return {
        (context.tonic.pitch_class + interval) % 12 for interval in MODE_INTERVALS[context.mode]
    }


def role_for_pitch(pitch: int, harmony: HarmonyEvent) -> HarmonicRole:
    chord = harmony.chord
    pitch_class = pitch % 12
    if chord is None:
        tones = scale_pitch_classes(harmony.key_context)
        return HarmonicRole.SCALE_TONE if pitch_class in tones else HarmonicRole.PASSING
    root = chord.bass_note or chord.root
    interval = (pitch_class - chord.root.pitch_class) % 12
    if pitch_class == root.pitch_class:
        return HarmonicRole.ROOT
    if pitch_class not in chord.pitch_classes:
        tones = scale_pitch_classes(harmony.key_context)
        return HarmonicRole.SCALE_TONE if pitch_class in tones else HarmonicRole.PASSING
    if interval in (3, 4):
        return HarmonicRole.THIRD
    if interval in (6, 7, 8):
        return HarmonicRole.FIFTH
    if interval in (9, 10, 11):
        return HarmonicRole.SEVENTH
    return HarmonicRole.EXTENSION
