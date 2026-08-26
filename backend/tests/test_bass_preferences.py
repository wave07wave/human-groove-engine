from __future__ import annotations

from app.bass.generation import generate_bass_pattern
from app.bass.models import BassGenerateRequest, BassPreferenceRequest
from app.bass.persistence import BassDatabase
from app.bass.preference import personal_preference_score, preference_features


def candidates_with_contrast():
    request = BassGenerateRequest(
        bars=4,
        harmony="Dm7 | G7 | Cmaj7 | A7",
        seed=817,
        candidate_count=2,
    )
    return generate_bass_pattern(request, 0), generate_bass_pattern(request, 5)


def test_pairwise_logistic_learning_builds_ranges_and_scores_winner_higher(tmp_path) -> None:
    database = BassDatabase(tmp_path / "preferences.db")
    preferred, rejected = candidates_with_contrast()
    assert preference_features(preferred) != preference_features(rejected)

    for _ in range(16):
        database.save_preference(
            BassPreferenceRequest(
                candidate_a=preferred,
                candidate_b=rejected,
                selected="A",
                display_order=[preferred.pattern_id, rejected.pattern_id],
            )
        )

    profile = database.preference_summary()
    assert profile.comparisons == 16
    assert profile.personal_weight > 0.5
    assert profile.preferred_ranges
    assert all(value.observations == 16 for value in profile.preferred_ranges.values())
    assert all(value.low <= value.mean <= value.high for value in profile.preferred_ranges.values())
    assert personal_preference_score(preferred, profile) > personal_preference_score(
        rejected, profile
    )


def test_empty_preference_profile_is_generic_and_uncertain(tmp_path) -> None:
    profile = BassDatabase(tmp_path / "empty.db").preference_summary()
    assert profile.comparisons == 0
    assert profile.personal_weight == 0
    assert profile.feature_weights == {}
    assert profile.preferred_ranges == {}
