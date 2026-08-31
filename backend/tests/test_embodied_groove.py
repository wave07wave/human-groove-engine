from app.analysis.listener import analyze_pattern
from app.embodied_evaluation import calibrate_motor_tempo, save_embodied_evaluation
from app.engine.generator import generate_pattern
from app.engine.optimizer import generate_candidate_pool
from app.models.evaluation import (
    EmbodiedEvaluationRequest,
    MotorTempoCalibrationRequest,
)
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.persistence.database import GrooveDatabase


def _pattern():
    return generate_pattern(
        bpm=108,
        bars=4,
        meter=MeterDefinition.from_name("4/4"),
        intent=GrooveIntent(),
        seed=92,
        performance_mode="rule",
        style="House",
    )


def test_embodied_analysis_separates_scaffold_timing_and_renewal() -> None:
    pattern = _pattern()
    analysis = analyze_pattern(pattern, include_render=True)

    assert analysis.embodied is not None
    assert analysis.embodied.motor_scaffold.tactus.clarity >= 0
    assert analysis.embodied.timing_coherence.independent_jitter >= 0
    assert analysis.embodied.phrase_renewal.motif_memory >= 0
    assert analysis.embodied.low_end_motion.render_applicable
    assert analysis.rendered_audio is not None
    assert analysis.rendered_audio.low_frequency_flux is not None


def test_comfortable_tap_and_embodied_feedback_are_optional_and_persisted(tmp_path) -> None:
    db = GrooveDatabase(tmp_path / "embodied.db")
    session_id = "embodied-test-001"
    profile = calibrate_motor_tempo(
        MotorTempoCalibrationRequest(
            anonymous_session_id=session_id,
            timestamps_ms=[float(index * 500) for index in range(16)],
        ),
        db,
    )
    assert profile.bpm == 120
    assert profile.confidence > 0.9
    assert db.motor_tempo_profile(session_id) == profile

    result = save_embodied_evaluation(
        EmbodiedEvaluationRequest(
            anonymous_session_id=session_id,
            pattern=_pattern(),
            urge_to_move=82,
            pleasure=77,
            beat_clarity=91,
        ),
        db,
    )
    assert result.accepted
    assert result.evidence_class == "self_report"

    for index in range(7):
        save_embodied_evaluation(
            EmbodiedEvaluationRequest(
                anonymous_session_id=session_id,
                pattern=_pattern(),
                urge_to_move=70 + index,
                pleasure=72,
                beat_clarity=84,
            ),
            db,
        )
    summary = db.embodied_evaluation_summary(session_id)
    assert summary.total_evaluations == 8
    assert summary.operator_arms[0].evaluations == 8
    assert summary.sufficient_for_personal_comparison


def test_embodied_challenge_changes_a_four_bar_phrase_and_is_honest_when_too_short() -> None:
    meter = MeterDefinition.from_name("4/4")
    calm = GrooveIntent()
    challenging = GrooveIntent()
    challenging.embodied.challenge = 0.9
    baseline = generate_pattern(
        bpm=108, bars=4, meter=meter, intent=calm, seed=77, performance_mode="rule"
    )
    changed = generate_pattern(
        bpm=108, bars=4, meter=meter, intent=challenging, seed=77, performance_mode="rule"
    )
    short = generate_pattern(
        bpm=108, bars=2, meter=meter, intent=challenging, seed=77, performance_mode="rule"
    )
    three_bar = generate_pattern(
        bpm=108, bars=3, meter=meter, intent=challenging, seed=77, performance_mode="rule"
    )

    assert [(event.event_id, event.primary_role) for event in changed.events] != [
        (event.event_id, event.primary_role) for event in baseline.events
    ]
    assert changed.metadata.embodied_operator_arm.startswith("challenge")
    assert three_bar.metadata.embodied_operator_arm.startswith("challenge")
    assert short.metadata.embodied_operator_arm == "baseline"


def test_optimizer_preserves_requested_embodied_intent() -> None:
    meter = MeterDefinition.from_name("4/4")
    calm = GrooveIntent()
    challenging = GrooveIntent()
    challenging.embodied.challenge = 0.9
    calm_candidates = generate_candidate_pool(
        bpm=108, bars=4, meter=meter, intent=calm, seed=808, performance_mode="rule"
    )
    challenge_candidates = generate_candidate_pool(
        bpm=108, bars=4, meter=meter, intent=challenging, seed=808, performance_mode="rule"
    )

    assert all(candidate.intent.embodied.challenge == 0 for candidate in calm_candidates)
    assert all(candidate.intent.embodied.challenge == 0.9 for candidate in challenge_candidates)
    assert [candidate.events for candidate in calm_candidates] != [
        candidate.events for candidate in challenge_candidates
    ]
