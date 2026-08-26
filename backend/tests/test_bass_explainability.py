from __future__ import annotations

from fastapi.testclient import TestClient

from app.bass.generation import generate_bass_pattern
from app.bass.harmony import harmony_at, role_for_pitch
from app.bass.models import BassGenerateRequest, HarmonicRole, MutationOperation
from app.bass.mutation import mutate_bass_pattern
from app.main import app


def source_pattern():
    return generate_bass_pattern(
        BassGenerateRequest(bars=4, harmony="Dm7 | G7 | Cmaj7 | A7", seed=423)
    )


def test_generated_notes_have_complete_decision_traces() -> None:
    pattern = source_pattern()
    assert pattern.events
    for event in pattern.events:
        trace = event.decision_trace
        assert trace is not None
        assert "metric gravity" in trace.onset_reason
        assert "functions as" in trace.pitch_reason
        assert "ticks" in trace.duration_reason
        assert "preferred center" in trace.octave_reason
        assert "velocity" in trace.articulation_reason
        assert set(trace.factors) >= {"metric_gravity", "structural_weight", "human_feel"}


def test_regeneration_refreshes_trace_and_records_operation() -> None:
    result = mutate_bass_pattern(source_pattern(), set(), MutationOperation.PITCH_ONLY)
    changed = next(
        event for event in result.events if event.provenance.mutation_operation == "pitch_only"
    )
    assert changed.decision_trace is not None
    assert changed.decision_trace.onset_reason.startswith("After pitch only regeneration")


def test_explain_api_returns_trace_and_rejects_unknown_event() -> None:
    client = TestClient(app)
    pattern = source_pattern()
    event = pattern.events[0]
    response = client.post(
        f"/api/v1/bass/explain/{event.event_id}", json=pattern.model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    assert response.json()["pitch_reason"] == event.decision_trace.pitch_reason

    missing = client.post(
        "/api/v1/bass/explain/missing", json=pattern.model_dump(mode="json")
    )
    assert missing.status_code == 404


def test_evaluate_refreshes_user_edited_role_analysis_and_trace_without_changing_intent() -> None:
    client = TestClient(app)
    pattern = source_pattern()
    event = next(
        item
        for item in pattern.events
        if item.harmonic_role
        in {
            HarmonicRole.ROOT,
            HarmonicRole.THIRD,
            HarmonicRole.FIFTH,
            HarmonicRole.SEVENTH,
        }
    )
    original_intent = pattern.intent.model_dump()
    event.pitch = min(pattern.register_limits.highest_midi_note, event.pitch + 1)
    event.provenance.origin = "user_edited"
    expected_role = role_for_pitch(event.pitch, harmony_at(pattern.harmony, event.grid_tick))
    pattern.analysis = None
    event.decision_trace = None

    response = client.post("/api/v1/bass/evaluate", json=pattern.model_dump(mode="json"))

    assert response.status_code == 200, response.text
    evaluated = response.json()
    edited = next(item for item in evaluated["events"] if item["event_id"] == event.event_id)
    assert edited["harmonic_role"] == expected_role.value
    assert edited["decision_trace"] is not None
    assert evaluated["analysis"] is not None
    assert evaluated["intent"] == original_intent
