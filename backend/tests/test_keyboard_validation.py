from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.keyboard.generation import (
    generate_keyboard_pattern,
    regenerate_keyboard_pattern,
)
from app.keyboard.models import (
    KEYBOARD_ANALYSIS_VERSION,
    KEYBOARD_GENERATION_VERSION,
    LEGACY_KEYBOARD_ANALYSIS_VERSION,
    LEGACY_KEYBOARD_GENERATION_VERSION,
    KeyboardGenerateRequest,
    KeyboardPattern,
    KeyboardRhythmContext,
)
from app.keyboard.persistence import KeyboardDatabase
from app.main import app


def _payload() -> dict:
    pattern = generate_keyboard_pattern(
        KeyboardGenerateRequest(bars=2, seed=519, candidate_count=1)
    )
    return pattern.model_dump(mode="json")


def test_generated_and_legacy_keyboard_versions_are_distinguishable() -> None:
    payload = _payload()
    assert payload["metadata"]["keyboard_generation_version"] == (
        KEYBOARD_GENERATION_VERSION
    )
    assert payload["metadata"]["keyboard_analysis_version"] == (
        KEYBOARD_ANALYSIS_VERSION
    )

    payload["metadata"].pop("keyboard_generation_version")
    payload["metadata"].pop("keyboard_analysis_version")
    legacy = KeyboardPattern.model_validate(payload)
    assert (
        legacy.metadata.keyboard_generation_version
        == LEGACY_KEYBOARD_GENERATION_VERSION
    )
    assert legacy.metadata.keyboard_analysis_version == LEGACY_KEYBOARD_ANALYSIS_VERSION

    capabilities = TestClient(app).get("/api/v1/keyboard/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["generation_version"] == KEYBOARD_GENERATION_VERSION
    assert capabilities.json()["analysis_version"] == KEYBOARD_ANALYSIS_VERSION


def test_evaluation_and_mutation_accurately_upgrade_legacy_stage_versions() -> None:
    payload = _payload()
    payload["metadata"].pop("keyboard_generation_version")
    payload["metadata"].pop("keyboard_analysis_version")
    legacy = KeyboardPattern.model_validate(payload)

    evaluated = TestClient(app).post("/api/v1/keyboard/evaluate", json=payload)
    assert evaluated.status_code == 200
    evaluated_metadata = evaluated.json()["metadata"]
    assert (
        evaluated_metadata["keyboard_generation_version"]
        == LEGACY_KEYBOARD_GENERATION_VERSION
    )
    assert evaluated_metadata["keyboard_analysis_version"] == KEYBOARD_ANALYSIS_VERSION

    regenerated = regenerate_keyboard_pattern(legacy, {0})
    assert regenerated.metadata.keyboard_generation_version == KEYBOARD_GENERATION_VERSION
    assert regenerated.metadata.keyboard_analysis_version == KEYBOARD_ANALYSIS_VERSION


@pytest.mark.parametrize(
    ("change_payload", "message"),
    [
        (lambda value: value["harmony"].update(events=[]), "cannot be empty"),
        (
            lambda value: value["harmony"]["events"][0].update(
                start_tick=1,
                duration_tick=value["harmony"]["events"][0]["duration_tick"] - 1,
            ),
            "continuous from tick zero",
        ),
    ],
)
def test_evaluate_api_rejects_incomplete_harmony(
    change_payload, message: str
) -> None:
    payload = _payload()
    change_payload(payload)
    response = TestClient(app).post("/api/v1/keyboard/evaluate", json=payload)
    assert response.status_code == 422
    assert message in response.text


def test_legacy_payload_limits_do_not_break_saved_library_loading(tmp_path) -> None:
    payload = _payload()
    payload["pattern_id"] = "旧-" + "x" * 500
    payload["name"] = ""
    payload["harmony_text"] = ""
    payload["harmony"]["events"] = []
    payload["tempo_map"]["segments"].append(
        {"start_tick": payload["bars"] * 3840, "bpm": 120}
    )
    payload["rhythm_context"]["kick_ticks"] = list(range(8193))
    legacy = KeyboardPattern.model_validate(payload)

    database = KeyboardDatabase(tmp_path / "legacy-keyboard.db")
    database.save_pattern(legacy)
    restored = database.saved_patterns()
    assert len(restored) == 1
    assert restored[0].pattern_id == payload["pattern_id"]
    assert restored[0].name == ""
    assert restored[0].harmony.events == []

    with pytest.raises(ValidationError, match="rhythm context is too large"):
        KeyboardGenerateRequest(
            rhythm_context=KeyboardRhythmContext(kick_ticks=list(range(8193)))
        )


def test_regeneration_repairs_a_legacy_incomplete_harmony_timeline() -> None:
    payload = _payload()
    payload["harmony"]["events"] = []
    legacy = KeyboardPattern.model_validate(payload)

    regenerated = regenerate_keyboard_pattern(legacy, {0})

    assert regenerated.harmony.events[0].start_tick == 0
    last = regenerated.harmony.events[-1]
    assert last.start_tick + last.duration_tick == (
        regenerated.bars * regenerated.meter.bar_ticks
    )


def test_midi_api_safely_encodes_header_newlines_from_legacy_ids() -> None:
    payload = _payload()
    payload["pattern_id"] = "keys\r\nInjected-Header"
    response = TestClient(app).post("/api/v1/keyboard/export-midi", json=payload)
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert "%0D%0A" in disposition


def test_midi_api_safely_exports_legacy_unicode_pattern_ids() -> None:
    payload = _payload()
    payload["pattern_id"] = "鍵盤-pattern"
    response = TestClient(app).post("/api/v1/keyboard/export-midi", json=payload)
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert 'filename="pattern.mid"' in disposition
    assert "filename*=UTF-8''%E9%8D%B5%E7%9B%A4-pattern.mid" in disposition
