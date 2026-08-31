from copy import deepcopy

from app.models.groove import GrooveDNA, GrooveIntent


def _intent(**values: float) -> GrooveIntent:
    base = GrooveDNA().model_dump()
    base.update(values)
    return GrooveIntent(target_dna=GrooveDNA(**base))


PRESETS: dict[str, GrooveIntent] = {
    "Balanced": _intent(),
    "Funk": _intent(
        pulse_stability=0.86,
        syncopation=0.75,
        interlock=0.9,
        ghost_density=0.62,
        recovery_strength=0.84,
        density=0.62,
    ),
    "Hip Hop": _intent(
        pulse_stability=0.88,
        syncopation=0.58,
        density=0.48,
        repetition=0.8,
        microtiming=0.56,
        low_end_anchor=0.84,
        ghost_density=0.34,
    ),
    "House": _intent(
        pulse_stability=0.94,
        beat_salience=0.92,
        density=0.68,
        repetition=0.86,
        interlock=0.82,
        low_end_anchor=0.9,
        variation=0.3,
    ),
    "Rock": _intent(
        pulse_stability=0.92,
        beat_salience=0.88,
        density=0.62,
        low_end_anchor=0.88,
        motor_affordance=0.9,
        velocity_contrast=0.64,
        recovery_strength=0.82,
    ),
    "Laid Back": _intent(
        pulse_stability=0.82, microtiming=0.58, swing=0.28, syncopation=0.42, density=0.42
    ),
    "Forward": _intent(
        pulse_stability=0.82, anticipation=0.68, microtiming=0.38, density=0.62, surprise=0.42
    ),
    "Hypnotic": _intent(
        pulse_stability=0.92,
        repetition=0.94,
        variation=0.22,
        surprise=0.25,
        hypnotic=0.92,
        microtiming=0.42,
    ),
    "Broken": _intent(
        pulse_stability=0.78,
        beat_salience=0.58,
        syncopation=0.82,
        metric_ambiguity=0.62,
        recovery_strength=0.9,
        surprise=0.7,
    ),
    "Minimal": _intent(
        pulse_stability=0.88, density=0.23, repetition=0.82, variation=0.2, syncopation=0.25
    ),
    "Swing": _intent(
        pulse_stability=0.82,
        swing=0.78,
        syncopation=0.55,
        velocity_contrast=0.58,
        duration_contrast=0.48,
    ),
    "Mechanical": _intent(
        pulse_stability=0.96,
        microtiming=0.02,
        variation=0.12,
        repetition=0.9,
        velocity_contrast=0.18,
    ),
    "Loose": _intent(
        pulse_stability=0.65,
        microtiming=0.82,
        variation=0.58,
        syncopation=0.55,
        recovery_strength=0.72,
    ),
}


def get_preset(name: str) -> GrooveIntent:
    return deepcopy(PRESETS.get(name, PRESETS["Balanced"]))
