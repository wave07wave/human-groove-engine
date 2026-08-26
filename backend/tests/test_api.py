from conftest import intent, meter
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_capabilities_and_presets():
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/capabilities").json()["audio_analysis"] is False
    assert "Funk" in client.get("/api/v1/presets").json()["built_in"]


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
