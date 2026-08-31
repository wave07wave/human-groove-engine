from types import SimpleNamespace

import pytest

from app.preference_scoring import (
    discriminative_range_evidence,
    preference_score_breakdown,
)


def preferred_range(*, uncertainty: float = 0.1, evidence: float = 1.0):
    return SimpleNamespace(
        mean=0.5,
        low=0.4,
        high=0.6,
        uncertainty=uncertainty,
        evidence=evidence,
    )


def test_range_score_can_learn_a_middle_optimum() -> None:
    ranges = {"density": preferred_range()}
    centre = preference_score_breakdown({"density": 0.5}, {}, ranges)
    low = preference_score_breakdown({"density": 0.1}, {}, ranges)
    high = preference_score_breakdown({"density": 0.9}, {}, ranges)

    assert centre.combined > low.combined
    assert centre.combined > high.combined
    assert low.combined == pytest.approx(high.combined)
    assert centre.range_mix == pytest.approx(0.45)


def test_uncertain_or_unsupported_ranges_do_not_move_the_score() -> None:
    uncertain = preference_score_breakdown(
        {"density": 0.5}, {}, {"density": preferred_range(uncertainty=1)}
    )
    unsupported = preference_score_breakdown(
        {"density": 0.5}, {}, {"density": preferred_range(evidence=0)}
    )

    assert uncertain.combined == pytest.approx(0.5)
    assert unsupported.combined == pytest.approx(0.5)
    assert uncertain.range_mix == 0
    assert unsupported.range_mix == 0


def test_directional_preference_remains_available_without_ranges() -> None:
    low = preference_score_breakdown({"syncopation": 0.1}, {"syncopation": 4}, {})
    high = preference_score_breakdown({"syncopation": 0.9}, {"syncopation": 4}, {})

    assert high.combined > low.combined
    assert high.combined == high.directional


def test_range_evidence_requires_a_winner_loser_distance_advantage() -> None:
    pairs = [
        ({"density": 0.45, "timing": 0.3}, {"density": 0.05, "timing": 0.3}, 1.0),
        ({"density": 0.55, "timing": 0.3}, {"density": 0.95, "timing": 0.3}, 0.7),
    ]

    density = discriminative_range_evidence(
        "density", mean=0.5, low=0.35, high=0.65, pairs=pairs
    )
    timing = discriminative_range_evidence(
        "timing", mean=0.3, low=0.2, high=0.4, pairs=pairs
    )

    assert density > 0.9
    assert timing == 0


def test_contradictory_range_comparisons_cancel_instead_of_creating_false_evidence() -> None:
    pairs = [
        ({"density": 0.5}, {"density": 0.1}, 1.0),
        ({"density": 0.1}, {"density": 0.5}, 1.0),
    ]

    evidence = discriminative_range_evidence(
        "density", mean=0.5, low=0.4, high=0.6, pairs=pairs
    )

    assert evidence == 0
