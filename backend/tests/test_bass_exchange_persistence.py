from __future__ import annotations

from fastapi.testclient import TestClient

from app.bass.generation import generate_bass_pattern
from app.bass.models import BassGenerateRequest, BassPreferenceRequest
from app.bass.persistence import BassDatabase
from app.main import app


def source_pattern(candidate: int = 0):
    request = BassGenerateRequest(bars=2, harmony="Dm7 | G7", seed=629)
    return generate_bass_pattern(request, candidate)


def test_pattern_library_and_versioned_histories(tmp_path) -> None:
    database = BassDatabase(tmp_path / "library.db")
    left, right = source_pattern(0), source_pattern(1)
    database.save_pattern(left)
    database.save_generation(left)
    database.save_preference(
        BassPreferenceRequest(
            candidate_a=left,
            candidate_b=right,
            selected="B",
            display_order=[right.pattern_id, left.pattern_id],
        )
    )

    assert database.saved_patterns()[0].model_dump() == left.model_dump()
    assert database.generation_history(1)[0].pattern_id == left.pattern_id
    assert database.generation_pattern(left.pattern_id).model_dump() == left.model_dump()
    assert database.generation_pattern("missing") is None
    preference = database.preference_history(1)[0]
    assert preference.selected == "B"
    assert preference.display_order == [right.pattern_id, left.pattern_id]
    assert preference.schema_version == "1.0"
    assert database.delete_pattern(left.pattern_id) is True
    assert database.delete_pattern(left.pattern_id) is False
    assert database.saved_patterns() == []


def test_pattern_exchange_contract_and_version_rejection() -> None:
    client = TestClient(app)
    pattern = source_pattern()
    exported = client.post(
        "/api/v1/bass/exchange/pattern/export", json=pattern.model_dump(mode="json")
    )
    assert exported.status_code == 200, exported.text
    payload = exported.json()
    assert payload["kind"] == "human_bass_pattern"
    assert payload["schema_version"] == "1.0"
    assert payload["pattern"]["pattern_id"] == pattern.pattern_id

    payload["schema_version"] = "99.0"
    rejected = client.post("/api/v1/bass/exchange/pattern/import", json=payload)
    assert rejected.status_code == 422


def test_generation_history_pattern_api_loads_a_saved_generation() -> None:
    client = TestClient(app)
    generated = client.post(
        "/api/v1/bass/generate",
        json={"bars": 2, "harmony": "Dm7 | G7", "candidate_count": 1, "seed": 817},
    )
    assert generated.status_code == 200, generated.text
    pattern_id = generated.json()["candidates"][0]["pattern_id"]

    loaded = client.get(f"/api/v1/bass/history/generations/{pattern_id}")
    missing = client.get("/api/v1/bass/history/generations/missing")

    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["pattern_id"] == pattern_id
    assert missing.status_code == 404


def test_saved_pattern_delete_api_round_trip() -> None:
    client = TestClient(app)
    pattern = source_pattern()
    payload = pattern.model_dump(mode="json")
    assert client.post("/api/v1/bass/patterns", json=payload).status_code == 200
    deleted = client.delete(f"/api/v1/bass/patterns/{pattern.pattern_id}")
    assert deleted.status_code == 204
    assert all(
        item["pattern_id"] != pattern.pattern_id
        for item in client.get("/api/v1/bass/patterns").json()
    )
    assert client.delete(f"/api/v1/bass/patterns/{pattern.pattern_id}").status_code == 404
