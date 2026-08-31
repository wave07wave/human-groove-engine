from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.bass.interaction import IntegrationMode, JointGenerationResult
from app.bass.models import GrooveContext
from app.config import PPQ, SCHEMA_VERSION
from app.main import app

FIXTURE = Path(__file__).parents[1] / "golden" / "integration-contract.json"


def test_frozen_integration_contract_matches_runtime_schema() -> None:
    contract = json.loads(FIXTURE.read_text(encoding="utf-8"))
    context = GrooveContext.model_validate(contract["groove_context"])

    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["ppq"] == PPQ
    assert contract["integration_modes"] == [mode.value for mode in IntegrationMode]
    assert context.tempo_map.segments[0].start_tick == 0
    assert set(contract["required_joint_result_fields"]) == set(
        JointGenerationResult.model_fields
    )


def test_openapi_exposes_frozen_integration_boundary() -> None:
    schema = app.openapi()
    assert "/api/v1/bass/context/from-groove" in schema["paths"]
    assert "/api/v1/interaction/generate" in schema["paths"]
    components = schema["components"]["schemas"]
    for name in (
        "GrooveContext-Input",
        "GrooveContext-Output",
        "JointGenerateRequest",
        "JointGenerateResponse",
        "RhythmBassInteractionDNA",
    ):
        assert name in components


def test_engine_capabilities_advertise_a_compatible_joint_contract() -> None:
    client = TestClient(app)
    groove = client.get("/api/v1/capabilities").json()
    bass = client.get("/api/v1/bass/capabilities").json()
    interaction = client.get("/api/v1/interaction/capabilities").json()

    assert groove["long_form_bars"] == bass["long_form_bars"] == 64
    assert bass["groove_context"] is True
    assert bass["joint_optimizer"] is True
    assert interaction["modes"] == [mode.value for mode in IntegrationMode]
    assert interaction["shared_complexity_budget"] is True
    assert interaction["lock_preservation"] is True
    assert interaction["reference_render_analysis"] is True
