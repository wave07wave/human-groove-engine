from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.bass.generation import generate_bass_pattern
from app.bass.models import (
    BassGenerateRequest,
    BassPreferenceRequest,
    BassPreferenceSummary,
    PreferenceRange,
)
from app.bass.persistence import BassDatabase
from app.bass.preference import (
    blended_candidate_score,
    personal_preference_score,
    preference_features,
)


def candidates_with_contrast(*, preset: str = "Supportive", seed: int = 817):
    request = BassGenerateRequest(
        bars=4,
        harmony="Dm7 | G7 | Cmaj7 | A7",
        seed=seed,
        candidate_count=2,
        preset=preset,
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

    profile = database.preference_summary("Supportive")
    assert profile.comparisons == 16
    assert profile.effective_comparisons == pytest.approx(4)
    assert profile.personal_weight == pytest.approx(.128)
    assert profile.preferred_ranges
    assert any(value.evidence > 0 for value in profile.preferred_ranges.values())
    assert all(value.observations == 1 for value in profile.preferred_ranges.values())
    assert all(value.low <= value.mean <= value.high for value in profile.preferred_ranges.values())
    assert personal_preference_score(preferred, profile) > personal_preference_score(
        rejected, profile
    )
    assert profile.profile_scope == "Supportive"


def test_bass_personal_score_prefers_an_evidence_backed_middle_value() -> None:
    profile = BassPreferenceSummary(
        comparisons=12,
        personal_weight=0.4,
        preferred_ranges={
            "syncopation": PreferenceRange(
                mean=0.5,
                low=0.4,
                high=0.6,
                uncertainty=0.1,
                observations=12,
                evidence=1,
            )
        },
    )
    low, centre = candidates_with_contrast(seed=819)
    high, _ = candidates_with_contrast(seed=820)
    low.analysis.atomic.syncopation_index = 0.1
    centre.analysis.atomic.syncopation_index = 0.5
    high.analysis.atomic.syncopation_index = 0.9
    for pattern in (low, centre, high):
        pattern.analysis.fitness = 0.5

    centre_score = personal_preference_score(centre, profile)
    assert centre_score > personal_preference_score(low, profile)
    assert centre_score > personal_preference_score(high, profile)
    assert blended_candidate_score(centre, profile) > blended_candidate_score(low, profile)
    assert blended_candidate_score(centre, profile) > blended_candidate_score(high, profile)


def test_empty_preference_profile_is_generic_and_uncertain(tmp_path) -> None:
    profile = BassDatabase(tmp_path / "empty.db").preference_summary()
    assert profile.comparisons == 0
    assert profile.personal_weight == 0
    assert profile.feature_weights == {}
    assert profile.preferred_ranges == {}


def test_bass_preference_profiles_are_isolated_by_preset(tmp_path) -> None:
    database = BassDatabase(tmp_path / "preferences.db")
    supportive = candidates_with_contrast(preset="Supportive", seed=827)
    walking = candidates_with_contrast(preset="Walking", seed=837)
    database.save_preference(
        BassPreferenceRequest(candidate_a=supportive[0], candidate_b=supportive[1], selected="A")
    )
    database.save_preference(
        BassPreferenceRequest(candidate_a=walking[0], candidate_b=walking[1], selected="B")
    )

    assert database.preference_summary("Supportive").comparisons == 1
    assert database.preference_summary("Walking").comparisons == 1
    assert database.preference_summary("Pedal").comparisons == 0
    assert database.preference_summary().comparisons == 2


def test_bass_preference_submission_is_idempotent(tmp_path) -> None:
    database = BassDatabase(tmp_path / "preferences.db")
    left, right = candidates_with_contrast()
    comparison = BassPreferenceRequest(
        candidate_a=left,
        candidate_b=right,
        selected="A",
        comparison_id="bass-comparison-fixed-01",
        decision_time_ms=2100,
    )

    assert database.save_preference(comparison)
    assert not database.save_preference(comparison)
    assert database.preference_summary("Supportive").comparisons == 1
    with pytest.raises(ValueError, match="already been used"):
        database.save_preference(comparison.model_copy(update={"selected": "B"}))


def test_bass_ties_do_not_create_false_personal_confidence(tmp_path) -> None:
    database = BassDatabase(tmp_path / "preferences.db")
    for index in range(3):
        left, right = candidates_with_contrast(seed=850 + index)
        database.save_preference(
            BassPreferenceRequest(
                candidate_a=left,
                candidate_b=right,
                selected="tie",
                comparison_id=f"bass-tie-comparison-{index}",
            )
        )

    profile = database.preference_summary("Supportive")
    assert profile.comparisons == 3
    assert profile.decisive_comparisons == 0
    assert profile.ties == 3
    assert profile.effective_comparisons == 0
    assert profile.learning_confidence == 0
    assert profile.personal_weight == 0
    assert profile.preferred_ranges == {}


def test_server_reanalyzes_bass_candidates_before_learning(tmp_path) -> None:
    database = BassDatabase(tmp_path / "preferences.db")
    left, right = candidates_with_contrast(seed=861)
    expected = preference_features(left)
    left.analysis.atomic.syncopation_index = 0 if expected["syncopation"] else 1

    database.save_preference(
        BassPreferenceRequest(candidate_a=left, candidate_b=right, selected="A")
    )

    with database.connect() as connection:
        stored = json.loads(
            connection.execute("SELECT features_a FROM bass_preferences").fetchone()[0]
        )
    assert stored == pytest.approx(expected)


def test_legacy_bass_rows_are_reclassified_from_generation_history(tmp_path) -> None:
    path = tmp_path / "preferences.db"
    database = BassDatabase(path)
    left, right = candidates_with_contrast(preset="Walking", seed=871)
    database.save_generation(left)
    database.save_generation(right)
    database.save_preference(
        BassPreferenceRequest(candidate_a=left, candidate_b=right, selected="A")
    )
    with database.connect() as connection:
        connection.execute("UPDATE bass_preferences SET profile_scope='__global__'")

    migrated = BassDatabase(path)
    assert migrated.preference_summary("Walking").comparisons == 1
    assert migrated.preference_summary("Supportive").comparisons == 0


def test_bass_preference_rejects_invalid_pairs() -> None:
    supportive = candidates_with_contrast(preset="Supportive", seed=881)
    walking = candidates_with_contrast(preset="Walking", seed=891)
    with pytest.raises(ValidationError, match="must be distinct"):
        BassPreferenceRequest(
            candidate_a=supportive[0], candidate_b=supportive[0], selected="A"
        )
    with pytest.raises(ValidationError, match="same preset"):
        BassPreferenceRequest(
            candidate_a=supportive[0], candidate_b=walking[0], selected="A"
        )


def test_bass_preference_scope_is_trimmed_and_cannot_be_blank() -> None:
    assert BassGenerateRequest(preset="  Walking  ").preset == "Walking"
    with pytest.raises(ValidationError, match="must not be blank"):
        BassGenerateRequest(preset="   ")
