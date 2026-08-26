from __future__ import annotations

from copy import deepcopy

from .models import BassIntent, BassIntentDNA


def _intent(**values: float) -> BassIntent:
    dna = BassIntentDNA(**values)
    return BassIntent(target=dna)


BASS_PRESETS: dict[str, BassIntent] = {
    "Supportive": _intent(
        root_strength=0.88,
        chord_tone_strength=0.90,
        density=0.42,
        silence=0.34,
        melodic_motion=0.25,
        chromaticism=0.08,
    ),
    "Minimal": _intent(
        root_strength=0.90,
        chord_tone_strength=0.92,
        density=0.20,
        silence=0.72,
        repetition=0.82,
        variation=0.18,
    ),
    "Melodic": _intent(
        root_strength=0.54,
        chord_tone_strength=0.72,
        density=0.58,
        melodic_motion=0.82,
        register_motion=0.68,
        variation=0.62,
        approach_activity=0.48,
    ),
    "Funk": _intent(
        root_strength=0.64,
        chord_tone_strength=0.78,
        density=0.62,
        syncopation=0.78,
        kick_lock=0.72,
        kick_complement=0.66,
        duration_contrast=0.68,
        human_feel=0.56,
    ),
    "Walking": _intent(
        root_strength=0.55,
        chord_tone_strength=0.72,
        density=0.86,
        silence=0.08,
        stepwise_motion=0.86,
        approach_activity=0.62,
        chromaticism=0.34,
        melodic_motion=0.72,
    ),
    "Hypnotic": _intent(
        root_strength=0.78,
        chord_tone_strength=0.85,
        density=0.48,
        repetition=0.92,
        variation=0.16,
        human_feel=0.24,
    ),
    "Broken": _intent(
        root_strength=0.46,
        chord_tone_strength=0.64,
        density=0.52,
        silence=0.48,
        syncopation=0.76,
        variation=0.74,
        kick_complement=0.70,
    ),
    "Pedal": _intent(
        root_strength=0.92,
        chord_tone_strength=0.76,
        density=0.38,
        silence=0.40,
        melodic_motion=0.08,
        repetition=0.94,
        register_motion=0.05,
    ),
}


def preset_intent(name: str) -> BassIntent:
    if name not in BASS_PRESETS:
        raise ValueError(f"unknown bass preset: {name}")
    return deepcopy(BASS_PRESETS[name])
