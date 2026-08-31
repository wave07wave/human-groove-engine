from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol


class PreferenceRangeLike(Protocol):
    mean: float
    low: float
    high: float
    uncertainty: float
    evidence: float


PreferenceEvidencePair = tuple[Mapping[str, float], Mapping[str, float], float]

MAX_RANGE_FEATURES = 3
MAX_RANGE_MIX = 0.5
MIN_RANGE_RADIUS = 0.04


@dataclass(frozen=True)
class PreferenceScoreBreakdown:
    directional: float
    range_affinity: float
    range_reliability: float
    range_mix: float
    combined: float


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _sigmoid(logit: float) -> float:
    return 1 / (1 + math.exp(-max(-30, min(30, logit))))


def discriminative_range_evidence(
    feature: str,
    *,
    mean: float,
    low: float,
    high: float,
    pairs: Iterable[PreferenceEvidencePair],
) -> float:
    """Measure whether winners were closer to a range centre than losers.

    Merely observing several similar winners is not enough: a feature receives
    evidence only when the compared loser was farther from that preferred area.
    Repeated comparisons can be supplied with a diminished pair weight.
    """
    radius = max(MIN_RANGE_RADIUS, mean - low, high - mean)
    advantage = 0.0
    total_weight = 0.0
    for chosen, rejected, pair_weight in pairs:
        if feature not in chosen or feature not in rejected or pair_weight <= 0:
            continue
        chosen_distance = abs(float(chosen[feature]) - mean)
        rejected_distance = abs(float(rejected[feature]) - mean)
        normalized = (rejected_distance - chosen_distance) / radius
        advantage += pair_weight * max(-1.0, min(1.0, normalized))
        total_weight += pair_weight
    return _clamp(advantage / total_weight) if total_weight else 0.0


def preference_score_breakdown(
    features: Mapping[str, float],
    feature_weights: Mapping[str, float],
    preferred_ranges: Mapping[str, PreferenceRangeLike],
) -> PreferenceScoreBreakdown:
    """Combine monotonic preference and evidence-backed range proximity.

    Pairwise weights capture directions such as "more syncopation". Preferred
    ranges capture non-monotonic taste such as "medium density". Only the three
    best-supported ranges participate, limiting small-data overfitting.
    """
    logit = sum(feature_weights.get(key, 0.0) * value for key, value in features.items())
    directional = _sigmoid(logit)

    candidates: list[tuple[str, float, float]] = []
    for key, preferred in preferred_ranges.items():
        if key not in features:
            continue
        reliability = _clamp(preferred.evidence) * (1 - _clamp(preferred.uncertainty))
        if reliability <= 0:
            continue
        value = features[key]
        side_radius = (
            preferred.mean - preferred.low
            if value < preferred.mean
            else preferred.high - preferred.mean
        )
        radius = max(MIN_RANGE_RADIUS, side_radius)
        normalized_distance = abs(value - preferred.mean) / radius
        affinity = math.exp(-0.5 * normalized_distance**2)
        candidates.append((key, reliability, affinity))

    strongest = sorted(candidates, key=lambda item: (-item[1], item[0]))[:MAX_RANGE_FEATURES]
    if not strongest:
        return PreferenceScoreBreakdown(
            directional=directional,
            range_affinity=0.5,
            range_reliability=0.0,
            range_mix=0.0,
            combined=directional,
        )

    total_reliability = sum(reliability for _, reliability, _ in strongest)
    range_affinity = sum(
        reliability * affinity for _, reliability, affinity in strongest
    ) / total_reliability
    range_reliability = total_reliability / len(strongest)
    range_mix = MAX_RANGE_MIX * range_reliability
    combined = (1 - range_mix) * directional + range_mix * range_affinity
    return PreferenceScoreBreakdown(
        directional=directional,
        range_affinity=range_affinity,
        range_reliability=range_reliability,
        range_mix=range_mix,
        combined=_clamp(combined),
    )
