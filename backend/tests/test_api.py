from conftest import intent, meter
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_capabilities_and_presets():
    assert client.get("/health").json() == {"status": "ok"}
    capabilities = client.get("/api/v1/capabilities").json()
    assert capabilities["audio_analysis"] is False
    assert capabilities["learned_performance_model"]["active"] == "gmd-performance-v1"
    assert capabilities["learned_performance_model"]["training_hits"] == 324852
    assert capabilities["reference_render_analysis"] is True
    assert capabilities["blind_listening_evaluation"] is True
    assert capabilities["technical_quality_audit"] is True
    assert capabilities["preference_dimensions"] == 21
    assert capabilities["preference_scopes"] is True
    assert capabilities["preference_ties"] is True
    assert capabilities["genre_rhythm_language"] is True
    assert capabilities["idempotent_preference_trials"] is True
    audit = client.get("/api/v1/quality/audit")
    assert audit.status_code == 200 and audit.json()["passed"] is True
    assert {profile["profile_id"] for profile in capabilities["render_profiles"]} == {
        "studio-tight-v1",
        "warm-pocket-v1",
        "club-punch-v1",
        "vintage-dust-v1",
    }
    built_in = client.get("/api/v1/presets").json()["built_in"]
    assert {"Funk", "Hip Hop", "House", "Rock"} <= set(built_in)


def test_generate_evaluate_mutate_and_export_api():
    response = client.post(
        "/api/v1/generate",
        json={
            "bpm": 100,
            "bars": 2,
            "meter": meter().model_dump(),
            "intent": intent().model_dump(),
            "preset": "Balanced",
            "seed": 7,
            "mode": "preview",
            "candidate_count": 2,
        },
    )
    assert response.status_code == 200
    patterns = response.json()["candidates"]
    assert len(patterns) == 2
    assert response.json()["preference_profile"]["comparisons"] >= 0
    assert response.json()["preference_profile"]["profile_scope"] == "Balanced"
    assert client.post("/api/v1/evaluate", json=patterns[0]).status_code == 200
    mutated = client.post(
        "/api/v1/mutate",
        json={
            "pattern": patterns[0],
            "instruments": ["bass"],
            "bars": [1],
            "operation": "regenerate",
        },
    )
    assert mutated.status_code == 200
    midi = client.post("/api/v1/export-midi", json=patterns[0])
    assert midi.status_code == 200 and midi.headers["content-type"] == "audio/midi"


def test_preference_profile_query_keeps_styles_separate():
    funk = client.get("/api/v1/preferences?style=Funk")
    balanced = client.get("/api/v1/preferences?style=Balanced")
    assert funk.status_code == 200
    assert balanced.status_code == 200
    assert funk.json()["profile_scope"] == "Funk"
    assert balanced.json()["profile_scope"] == "Balanced"
