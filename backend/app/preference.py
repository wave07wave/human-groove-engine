from __future__ import annotations

from app.models.groove import GrooveDNA
from app.models.pattern import GroovePattern
from app.models.preference import GroovePreferenceSummary
from app.preference_scoring import preference_score_breakdown

# Preference learning follows the same public contract as generation and the
# technical control audit. A new Groove DNA dimension cannot silently ship
# without also becoming available to personal learning.
PREFERENCE_FEATURES = tuple(GrooveDNA.model_fields)


def preference_features(pattern: GroovePattern) -> dict[str, float]:
    """Normalized, audible Groove features used by pairwise learning."""
    if not pattern.analysis:
        return {}
    measured = pattern.analysis.measured_dna.model_dump()
    return {key: float(measured[key]) for key in PREFERENCE_FEATURES}


def personal_preference_score(
    pattern: GroovePattern, profile: GroovePreferenceSummary | None
) -> float:
    if not profile or not profile.comparisons:
        return 0.5
    features = preference_features(pattern)
    return preference_score_breakdown(
        features, profile.feature_weights, profile.preferred_ranges
    ).combined


def blended_candidate_score(
    pattern: GroovePattern, profile: GroovePreferenceSummary | None
) -> float:
    generic = pattern.analysis.fitness if pattern.analysis else 0
    weight = profile.personal_weight if profile else 0
    return (1 - weight) * generic + weight * personal_preference_score(pattern, profile)
