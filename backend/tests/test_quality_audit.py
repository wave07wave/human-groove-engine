from pathlib import Path

import pytest

from app.models.groove import GrooveDNA
from app.quality.audit import load_quality_audit, run_quality_audit


def test_bundled_quality_audit_matches_engine_and_disclaims_perception():
    report = load_quality_audit()
    assert report.passed is True
    assert report.perceptual_quality_claim is False
    assert tuple(item.dimension for item in report.controls) == tuple(GrooveDNA.model_fields)
    assert all(item.delta >= item.minimum_delta for item in report.controls)
    assert report.diversity.minimum_distance >= report.diversity.required_minimum_distance
    assert report.determinism.mismatches == 0
    assert report.latency.p95_seconds <= report.latency.maximum_p95_seconds


def test_quality_audit_runner_reproduces_all_gates():
    report = run_quality_audit()
    assert report.passed is True


def test_stale_quality_report_is_rejected(tmp_path: Path):
    report = load_quality_audit()
    stale = report.model_copy(update={"engine_version": "stale"})
    path = tmp_path / "stale.json"
    path.write_text(stale.model_dump_json(), encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not match"):
        load_quality_audit(path)
