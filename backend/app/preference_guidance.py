from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Mapping, Protocol


class PreferenceRangeLike(Protocol):
    mean: float
    uncertainty: float
    evidence: float


class PreferenceProfileLike(Protocol):
    comparisons: int
    learning_confidence: float
    feature_weights: Mapping[str, float]
    preferred_ranges: Mapping[str, PreferenceRangeLike]


MIN_GUIDANCE_CONFIDENCE = 0.2
MAX_GUIDANCE_BLEND = 0.35


@dataclass(frozen=True)
class PreferenceGuidance:
    values: dict[str, float]
    strength: float = 0.0
    features: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self.features)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def guided_feature_values(
    original_values: Mapping[str, float],
    feature_to_target: Mapping[str, str],
    profile: PreferenceProfileLike | None,
    *,
    disabled_features: AbstractSet[str] = frozenset(),
) -> PreferenceGuidance:
    """Build a bounded search target without changing the requested intent."""
    values = {key: float(value) for key, value in original_values.items()}
    if (
        profile is None
        or not profile.comparisons
        or profile.learning_confidence < MIN_GUIDANCE_CONFIDENCE
    ):
        return PreferenceGuidance(values=values)

    maximum_weight = max(
        (abs(float(weight)) for weight in profile.feature_weights.values()), default=0.0
    )
    changed: list[str] = []
    maximum_blend = 0.0
    for feature, target in feature_to_target.items():
        if feature in disabled_features or target not in values:
            continue
        weight = float(profile.feature_weights.get(feature, 0.0))
        directional_relevance = abs(weight) / maximum_weight if maximum_weight else 0.0
        preferred = profile.preferred_ranges.get(feature)
        range_reliability = (
            _clamp(preferred.evidence) * (1 - _clamp(preferred.uncertainty))
            if preferred is not None
            else 0.0
        )
        use_range = range_reliability > 0 and range_reliability >= 0.5 * directional_relevance
        if use_range:
            desired = _clamp(preferred.mean)
            feature_strength = range_reliability
        elif directional_relevance > 0:
            desired = 1.0 if weight > 0 else 0.0
            feature_strength = directional_relevance
        else:
            continue
        blend = MAX_GUIDANCE_BLEND * _clamp(profile.learning_confidence) * feature_strength
        original = values[target]
        guided = _clamp(original + (desired - original) * blend)
        if abs(guided - original) <= 1e-9:
            continue
        values[target] = guided
        changed.append(feature)
        maximum_blend = max(maximum_blend, blend)

    return PreferenceGuidance(
        values=values,
        strength=maximum_blend,
        features=tuple(sorted(changed)),
    )
