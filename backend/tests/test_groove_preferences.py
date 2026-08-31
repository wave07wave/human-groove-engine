import json

import pytest
from conftest import intent, meter
from pydantic import ValidationError

from app.analysis.listener import analyze_pattern
from app.engine.generator import generate_pattern
from app.engine.mutation import regenerate_selected
from app.models.api import GenerateRequest, PreferenceRequest
from app.models.event import InstrumentID
from app.models.groove import GrooveDNA
from app.models.preference import GroovePreferenceRange, GroovePreferenceSummary
from app.persistence.database import GrooveDatabase
from app.preference import (
    PREFERENCE_FEATURES,
    blended_candidate_score,
    personal_preference_score,
    preference_features,
)


def generated(seed: int, *, style: str = "Balanced"):
    pattern = generate_pattern(
        bpm=104,
        bars=4,
        meter=meter(),
        intent=intent(microtiming=0.8),
        seed=seed,
        style=style,
    )
    pattern.analysis = analyze_pattern(pattern)
    return pattern


def test_style_pocket_changes_performance_without_changing_score():
    mechanical = generated(77, style="Mechanical")
    laid_back = generated(77, style="Laid Back")

    def score(pattern):
        return [
            (event.instrument, event.grid_tick, event.primary_role)
            for event in pattern.events
        ]

    assert score(mechanical) == score(laid_back)
    assert [event.micro_offset_us for event in mechanical.events] != [
        event.micro_offset_us for event in laid_back.events
    ]
    assert [event.velocity for event in mechanical.events] != [
        event.velocity for event in laid_back.events
    ]


def test_partial_regeneration_keeps_style_pocket():
    original = generated(93, style="Funk")
    changed = regenerate_selected(original, {InstrumentID.SNARE}, {1})
    assert changed.metadata.style == "Funk"
    assert changed.metadata.performance_model == original.metadata.performance_model


def test_pairwise_learning_builds_ranges_and_prefers_selected_pattern(tmp_path):
    preferred = generated(41, style="Funk")
    rejected = generated(42, style="Funk")
    database = GrooveDatabase(tmp_path / "preferences.db")
    for _ in range(12):
        database.save_preference(
            PreferenceRequest(candidate_a=preferred, candidate_b=rejected, selected="A")
        )
    profile = database.preference_summary("Funk")
    assert profile.comparisons == 12
    assert profile.decisive_comparisons == 12
    assert profile.effective_comparisons == pytest.approx(12**0.5)
    assert profile.personal_weight < 0.2
    assert profile.preferred_ranges
    assert any(value.evidence > 0 for value in profile.preferred_ranges.values())
    assert profile.personal_weight > 0
    assert personal_preference_score(preferred, profile) > personal_preference_score(
        rejected, profile
    )
    assert profile.profile_scope == "Funk"


def test_groove_personal_score_prefers_an_evidence_backed_middle_value():
    profile = GroovePreferenceSummary(
        comparisons=12,
        personal_weight=0.4,
        preferred_ranges={
            "syncopation": GroovePreferenceRange(
                mean=0.5,
                low=0.4,
                high=0.6,
                uncertainty=0.1,
                observations=12,
                evidence=1,
            )
        },
    )
    low, centre, high = generated(45), generated(46), generated(47)
    low.analysis.measured_dna.syncopation = 0.1
    centre.analysis.measured_dna.syncopation = 0.5
    high.analysis.measured_dna.syncopation = 0.9
    for pattern in (low, centre, high):
        pattern.analysis.fitness = 0.5

    centre_score = personal_preference_score(centre, profile)
    assert centre_score > personal_preference_score(low, profile)
    assert centre_score > personal_preference_score(high, profile)
    assert blended_candidate_score(centre, profile) > blended_candidate_score(low, profile)
    assert blended_candidate_score(centre, profile) > blended_candidate_score(high, profile)


def test_preference_profiles_are_isolated_by_style(tmp_path):
    database = GrooveDatabase(tmp_path / "preferences.db")
    funk = [generated(141 + index, style="Funk") for index in range(2)]
    balanced = [generated(151 + index, style="Balanced") for index in range(2)]
    database.save_preference(
        PreferenceRequest(candidate_a=funk[0], candidate_b=funk[1], selected="A")
    )
    database.save_preference(
        PreferenceRequest(candidate_a=balanced[0], candidate_b=balanced[1], selected="B")
    )

    assert database.preference_summary("Funk").comparisons == 1
    assert database.preference_summary("Balanced").comparisons == 1
    assert database.preference_summary("Mechanical").comparisons == 0
    assert database.preference_summary().comparisons == 2


def test_legacy_global_rows_are_reclassified_from_generation_history(tmp_path):
    path = tmp_path / "preferences.db"
    database = GrooveDatabase(path)
    left, right = generated(161, style="Funk"), generated(162, style="Funk")
    database.save_generation(left)
    database.save_generation(right)
    database.save_preference(
        PreferenceRequest(candidate_a=left, candidate_b=right, selected="A")
    )
    with database.connect() as connection:
        connection.execute("UPDATE preferences SET profile_scope='__global__'")

    migrated = GrooveDatabase(path)
    assert migrated.preference_summary("Funk").comparisons == 1
    assert migrated.preference_summary("Balanced").comparisons == 0


def test_preference_learning_covers_every_public_dna_dimension():
    assert set(PREFERENCE_FEATURES) == set(GrooveDNA.model_fields)


def test_preference_submission_is_idempotent(tmp_path):
    database = GrooveDatabase(tmp_path / "preferences.db")
    comparison = PreferenceRequest(
        candidate_a=generated(51),
        candidate_b=generated(52),
        selected="A",
        comparison_id="comparison-fixed-01",
        decision_time_ms=2400,
    )

    assert database.save_preference(comparison)
    assert not database.save_preference(comparison)
    assert database.preference_summary().comparisons == 1

    with pytest.raises(ValueError, match="already been used"):
        database.save_preference(comparison.model_copy(update={"selected": "B"}))


def test_ties_do_not_create_false_personal_confidence(tmp_path):
    database = GrooveDatabase(tmp_path / "preferences.db")
    for index in range(3):
        database.save_preference(
            PreferenceRequest(
                candidate_a=generated(60 + index * 2),
                candidate_b=generated(61 + index * 2),
                selected="tie",
                comparison_id=f"tie-comparison-{index}",
            )
        )

    profile = database.preference_summary()
    assert profile.comparisons == 3
    assert profile.decisive_comparisons == 0
    assert profile.ties == 3
    assert profile.effective_comparisons == 0
    assert profile.learning_confidence == 0
    assert profile.personal_weight == 0
    assert profile.preferred_ranges == {}


def test_server_reanalyzes_preference_candidates_before_learning(tmp_path):
    database = GrooveDatabase(tmp_path / "preferences.db")
    left = generated(71)
    right = generated(72)
    expected = preference_features(left)
    left.analysis.measured_dna.syncopation = 0 if expected["syncopation"] else 1

    database.save_preference(
        PreferenceRequest(candidate_a=left, candidate_b=right, selected="A")
    )

    with database.connect() as connection:
        stored = json.loads(
            connection.execute("SELECT features_a FROM preferences").fetchone()[0]
        )
    assert stored == pytest.approx(expected)


def test_preference_rejects_the_same_candidate_on_both_sides():
    pattern = generated(81)
    with pytest.raises(ValidationError, match="must be distinct"):
        PreferenceRequest(candidate_a=pattern, candidate_b=pattern, selected="A")


def test_preference_rejects_mixed_styles():
    with pytest.raises(ValidationError, match="same style"):
        PreferenceRequest(
            candidate_a=generated(82, style="Funk"),
            candidate_b=generated(83, style="Mechanical"),
            selected="A",
        )


def test_groove_preference_scope_is_trimmed_and_cannot_be_blank():
    assert GenerateRequest(preset="  Funk  ").preset == "Funk"
    assert generated(84, style="  Funk  ").metadata.style == "Funk"
    with pytest.raises(ValidationError, match="must not be blank"):
        GenerateRequest(preset="   ")
