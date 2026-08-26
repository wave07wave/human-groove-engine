from __future__ import annotations

from copy import deepcopy

from .models import BassIntent


def resolve_intent(intent: BassIntent) -> tuple[BassIntent, list[str]]:
    """Project conflicting soft targets into a feasible, musically useful region."""
    resolved = deepcopy(intent)
    target = resolved.target
    notes: list[str] = []

    if target.density > 0.72 and target.silence > 0.62:
        target.density = 0.72 + (target.density - 0.72) * 0.35
        target.duration_contrast = max(target.duration_contrast, 0.65)
        notes.append("high density + high silence resolved with shorter, contrasted notes")
    if target.chromaticism > 0.65 and target.chord_tone_strength > 0.75:
        target.approach_activity = max(target.approach_activity, target.chromaticism * 0.82)
        target.chromaticism = min(target.chromaticism, 0.78)
        notes.append("chromatic activity directed toward harmonic targets")
    if target.leap_activity > 0.70 and target.stepwise_motion > 0.75:
        target.leap_activity = 0.70
        notes.append("leap activity limited so stepwise recovery remains possible")
    if target.register_motion > 0.70 and target.density > 0.72:
        target.density *= 0.88
        notes.append("density reduced to preserve clarity during register motion")
    if not resolved.allow_chromatic_notes:
        target.chromaticism = 0
        target.approach_activity = min(target.approach_activity, 0.55)
    return resolved, notes
