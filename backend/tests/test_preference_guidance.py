from types import SimpleNamespace

import pytest

from app.preference_guidance import guided_feature_values


def profile(
    *,
    confidence: float = 1,
    weights: dict[str, float] | None = None,
    ranges: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        comparisons=12,
        learning_confidence=confidence,
        feature_weights=weights or {},
        preferred_ranges=ranges or {},
    )


def preferred_range(mean: float, *, evidence: float = 1, uncertainty: float = 0) -> object:
    return SimpleNamespace(mean=mean, evidence=evidence, uncertainty=uncertainty)


def test_low_confidence_leaves_search_targets_unchanged() -> None:
    original = {"density": 0.2}
    guidance = guided_feature_values(
        original,
        {"density": "density"},
        profile(
            confidence=0.19,
            weights={"density": 1},
            ranges={"density": preferred_range(0.8)},
        ),
    )

    assert guidance.values == original
    assert not guidance.active
    assert guidance.strength == 0


def test_reliable_middle_range_guides_toward_the_learned_center() -> None:
    guidance = guided_feature_values(
        {"density": 0.1},
        {"density": "density"},
        profile(
            weights={"density": 1},
            ranges={"density": preferred_range(0.5)},
        ),
    )

    assert guidance.values["density"] == pytest.approx(0.24)
    assert guidance.features == ("density",)
    assert guidance.strength == pytest.approx(0.35)


def test_directional_weight_is_used_when_range_evidence_is_too_weak() -> None:
    guidance = guided_feature_values(
        {"density": 0.8},
        {"density": "density"},
        profile(
            weights={"density": -1},
            ranges={"density": preferred_range(0.6, evidence=0.2)},
        ),
    )

    assert guidance.values["density"] == pytest.approx(0.52)
    assert guidance.strength == pytest.approx(0.35)


def test_reliable_middle_range_wins_over_an_extreme_direction() -> None:
    guidance = guided_feature_values(
        {"density": 0.2},
        {"density": "density"},
        profile(
            weights={"density": 1},
            ranges={"density": preferred_range(0.55, evidence=0.6)},
        ),
    )

    assert guidance.values["density"] == pytest.approx(0.2735)


def test_disabled_feature_is_never_guided() -> None:
    guidance = guided_feature_values(
        {"chromaticism": 0.1},
        {"chromatic_tolerance": "chromaticism"},
        profile(
            weights={"chromatic_tolerance": 1},
            ranges={"chromatic_tolerance": preferred_range(0.9)},
        ),
        disabled_features=frozenset({"chromatic_tolerance"}),
    )

    assert guidance.values["chromaticism"] == 0.1
    assert not guidance.active
