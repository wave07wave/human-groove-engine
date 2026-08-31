import sqlite3
from pathlib import Path

import pytest
from conftest import intent, meter
from pydantic import ValidationError

from app.evaluation import answer_blind_session, create_blind_session, evaluation_summary
from app.models.api import GenerateRequest
from app.models.evaluation import BlindResponseRequest, BlindSessionRequest
from app.persistence.database import GrooveDatabase


def request() -> BlindSessionRequest:
    return BlindSessionRequest(
        participant_group="drummer",
        consent=True,
        generation=GenerateRequest(
            bpm=104,
            bars=2,
            meter=meter(),
            intent=intent(microtiming=0.8),
            preset="Funk",
            seed=91,
            candidate_count=1,
        ),
    )


def test_blind_session_changes_performance_not_quantized_score(tmp_path: Path):
    database = GrooveDatabase(tmp_path / "evaluation.db")
    session = create_blind_session(request(), database)

    assert {item.position for item in session.candidates} == {"left", "right"}
    left, right = (item.pattern for item in session.candidates)
    assert [(event.instrument, event.grid_tick) for event in left.events] == [
        (event.instrument, event.grid_tick) for event in right.events
    ]
    assert left.metadata.performance_model == right.metadata.performance_model == "blind"
    assert left.analysis is None and right.analysis is None
    assert "learned" not in left.pattern_id and "rule" not in right.pattern_id
    assert any(
        (a.micro_offset_us, a.velocity) != (b.micro_offset_us, b.velocity)
        for a, b in zip(left.events, right.events, strict=True)
    )


def test_response_is_single_use_and_summary_is_grouped(tmp_path: Path):
    database = GrooveDatabase(tmp_path / "evaluation.db")
    session = create_blind_session(request(), database)
    response = BlindResponseRequest(
        session_id=session.session_id,
        selected="left",
        decision_time_ms=4200,
        saved_choice="left",
    )

    result = answer_blind_session(response, database)
    assert result.selected_variant in {"learned", "rule"}
    with pytest.raises(RuntimeError, match="already been answered"):
        answer_blind_session(response, database)

    summary = evaluation_summary(database)
    drummer = next(item for item in summary.groups if item.participant_group == "drummer")
    assert summary.completed == 1
    assert summary.verdict == "collecting"
    assert drummer.comparisons == 1
    assert drummer.saved_rate == 1


def test_consent_is_required():
    with pytest.raises(ValueError, match="consent is required"):
        BlindSessionRequest(
            participant_group="general",
            consent=False,
            generation=request().generation,
        )


def test_study_block_rejects_duplicate_trial_and_measures_repeat_consistency(tmp_path: Path):
    database = GrooveDatabase(tmp_path / "evaluation.db")
    first_request = request().model_copy(
        update={"study_run_id": "repeat-block-01", "trial_index": 0}
    )
    first = create_blind_session(first_request, database)
    with pytest.raises(ValueError, match="already been created"):
        create_blind_session(first_request, database)

    repeated_request = first_request.model_copy(update={"trial_index": 5})
    repeated = create_blind_session(repeated_request, database)

    for session in (first, repeated):
        row = database.blind_evaluation(session.session_id)
        assert row is not None
        selected = "left" if row["left_variant"] == "learned" else "right"
        answer_blind_session(
            BlindResponseRequest(
                session_id=session.session_id,
                selected=selected,
                decision_time_ms=3000,
            ),
            database,
        )

    summary = evaluation_summary(database)
    assert summary.eligible_repeat_pairs == 1
    assert summary.repeat_consistency == 1


def test_study_block_freezes_generation_settings_and_anchor(tmp_path: Path):
    database = GrooveDatabase(tmp_path / "evaluation.db")
    first_request = request().model_copy(
        update={"study_run_id": "frozen-block-01", "trial_index": 0}
    )
    create_blind_session(first_request, database)

    changed_generation = first_request.generation.model_copy(update={"bpm": 112})
    with pytest.raises(ValueError, match="settings cannot change"):
        create_blind_session(
            first_request.model_copy(
                update={"trial_index": 1, "generation": changed_generation}
            ),
            database,
        )

    wrong_anchor = first_request.generation.model_copy(
        update={"seed": first_request.generation.seed + 1}
    )
    with pytest.raises(ValueError, match="must repeat the first stimulus"):
        create_blind_session(
            first_request.model_copy(update={"trial_index": 5, "generation": wrong_anchor}),
            database,
        )


def test_saved_blind_choice_must_match_the_answer():
    with pytest.raises(ValidationError, match="must match"):
        BlindResponseRequest(
            session_id="blind-response-01",
            selected="left",
            saved_choice="right",
            decision_time_ms=1000,
        )


def test_phase_six_database_migrates_without_losing_evaluations(tmp_path: Path):
    path = tmp_path / "legacy-evaluation.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE blind_evaluations("
            "session_id TEXT PRIMARY KEY,participant_group TEXT NOT NULL,"
            "left_variant TEXT NOT NULL,right_variant TEXT NOT NULL,"
            "left_pattern TEXT NOT NULL,right_pattern TEXT NOT NULL,started_at TEXT NOT NULL,"
            "selected TEXT,decision_time_ms INTEGER,saved_choice TEXT,responded_at TEXT,"
            "schema_version TEXT NOT NULL)"
        )

    database = GrooveDatabase(path)
    with database.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(blind_evaluations)")
        }
    assert {"study_run_id", "trial_index", "stimulus_key", "study_config_key"} <= columns
