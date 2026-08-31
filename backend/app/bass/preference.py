from __future__ import annotations

import math

from app.preference_scoring import preference_score_breakdown

from .analysis import clamp
from .models import BassPattern, BassPreferenceSummary

PREFERENCE_FEATURES = (
    "syncopation",
    "density",
    "silence",
    "root_usage",
    "chromatic_tolerance",
    "pitch_motion",
    "register",
    "kick_relation",
    "timing",
    "duration",
)


def preference_features(pattern: BassPattern) -> dict[str, float]:
    """Return the normalized, user-facing feature vector used by pairwise learning."""
    if not pattern.analysis:
        return {}
    atomic, dna = pattern.analysis.atomic, pattern.analysis.dna
    kick_relation = dna.kick_relationship_quality
    return {
        "syncopation": clamp(atomic.syncopation_index),
        "density": clamp(atomic.onset_density * 1.7),
        "silence": clamp(atomic.silence_ratio),
        "root_usage": clamp(atomic.root_ratio),
        "chromatic_tolerance": clamp(atomic.chromatic_ratio * 4),
        "pitch_motion": clamp(dna.melodic_motion),
        "register": clamp((atomic.register_mean - 28) / 32),
        "kick_relation": clamp(kick_relation if kick_relation is not None else 0.5),
        "timing": clamp(dna.timing_character_strength),
        "duration": clamp(math.sqrt(max(0, atomic.duration_variance)) / 960),
    }


def personal_preference_score(
    pattern: BassPattern, profile: BassPreferenceSummary | None
) -> float:
    if not profile or not profile.comparisons:
        return 0.5
    features = preference_features(pattern)
    return preference_score_breakdown(
        features, profile.feature_weights, profile.preferred_ranges
    ).combined


def blended_candidate_score(
    pattern: BassPattern, profile: BassPreferenceSummary | None
) -> float:
    generic = pattern.analysis.fitness if pattern.analysis else 0
    weight = profile.personal_weight if profile else 0
    return (1 - weight) * generic + weight * personal_preference_score(pattern, profile)
