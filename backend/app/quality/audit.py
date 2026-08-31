from __future__ import annotations

import math
import platform
import statistics
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from app.analysis.listener import analyze_pattern
from app.config import ENGINE_VERSION
from app.engine.generator import generate_pattern
from app.engine.optimizer import generate_candidates, pattern_distance
from app.models.groove import GrooveDNA, GrooveIntent
from app.models.meter import MeterDefinition
from app.models.quality import (
    ControlResponseAudit,
    DeterminismAudit,
    DiversityAudit,
    LatencyAudit,
    QualityAuditReport,
)

REPORT_PATH = Path(__file__).resolve().parent / "reports" / "engine-quality-v1.json"
# Every public intent dimension must cause a measurable event-derived response.
# Keeping this derived from the schema makes newly added controls fail the audit
# until generation and analysis have both been wired deliberately.
CONTROL_DIMENSIONS = tuple(GrooveDNA.model_fields)
CONTROL_MINIMUM_DELTA = 0.01
DIVERSITY_MEAN_MINIMUM = 0.15
DIVERSITY_PAIR_MINIMUM = 0.08
LATENCY_P95_MAXIMUM = 0.75


def _pattern(
    *, seed: int, intent: GrooveIntent, performance_mode: str = "rule"
):
    pattern = generate_pattern(
        bpm=108,
        bars=4,
        meter=MeterDefinition.from_name("4/4"),
        intent=intent,
        seed=seed,
        performance_mode=performance_mode,
        render_profile="off",
    )
    pattern.analysis = analyze_pattern(pattern, include_render=False)
    return pattern


def run_quality_audit(control_seeds: tuple[int, ...] = tuple(range(10, 42))) -> QualityAuditReport:
    controls = []
    for dimension in CONTROL_DIMENSIONS:
        means = []
        for level in (0.2, 0.8):
            measured = []
            for seed in control_seeds:
                intent = GrooveIntent()
                setattr(intent.target_dna, dimension, level)
                analysis = _pattern(seed=seed, intent=intent).analysis
                measured.append(float(getattr(analysis.measured_dna, dimension)))
            means.append(statistics.fmean(measured))
        delta = means[1] - means[0]
        controls.append(
            ControlResponseAudit(
                dimension=dimension,
                low_mean=means[0],
                high_mean=means[1],
                delta=delta,
                minimum_delta=CONTROL_MINIMUM_DELTA,
                passed=delta >= CONTROL_MINIMUM_DELTA,
            )
        )

    distances = []
    latency_samples = []
    for seed in range(70, 75):
        started = perf_counter()
        candidates = generate_candidates(
            bpm=108,
            bars=4,
            meter=MeterDefinition.from_name("4/4"),
            intent=GrooveIntent(),
            seed=seed,
            count=4,
            performance_mode="rule",
            render_profile="off",
        )
        latency_samples.append(perf_counter() - started)
        distances.extend(
            pattern_distance(left, right)
            for index, left in enumerate(candidates)
            for right in candidates[index + 1 :]
        )
    diversity = DiversityAudit(
        comparisons=len(distances),
        mean_distance=statistics.fmean(distances),
        minimum_distance=min(distances),
        required_mean_distance=DIVERSITY_MEAN_MINIMUM,
        required_minimum_distance=DIVERSITY_PAIR_MINIMUM,
        passed=(
            statistics.fmean(distances) >= DIVERSITY_MEAN_MINIMUM
            and min(distances) >= DIVERSITY_PAIR_MINIMUM
        ),
    )

    mismatches = 0
    determinism_cases = 0
    for performance_mode in ("rule", "auto"):
        for seed in (91, 92, 93):
            left = _pattern(
                seed=seed, intent=GrooveIntent(), performance_mode=performance_mode
            )
            right = _pattern(
                seed=seed, intent=GrooveIntent(), performance_mode=performance_mode
            )
            determinism_cases += 1
            mismatches += left.model_dump_json() != right.model_dump_json()
    determinism = DeterminismAudit(
        cases=determinism_cases,
        mismatches=mismatches,
        passed=mismatches == 0,
    )

    ordered_latency = sorted(latency_samples)
    p95_index = max(0, math.ceil(len(ordered_latency) * 0.95) - 1)
    latency = LatencyAudit(
        samples=len(latency_samples),
        median_seconds=statistics.median(latency_samples),
        p95_seconds=ordered_latency[p95_index],
        maximum_p95_seconds=LATENCY_P95_MAXIMUM,
        passed=ordered_latency[p95_index] <= LATENCY_P95_MAXIMUM,
    )
    passed = all(item.passed for item in controls) and all(
        item.passed for item in (diversity, determinism, latency)
    )
    return QualityAuditReport(
        engine_version=ENGINE_VERSION,
        generated_at=datetime.now(UTC).isoformat(),
        runtime=f"Python {platform.python_version()} · {platform.system()} {platform.machine()}",
        control_seed_count=len(control_seeds),
        controls=controls,
        diversity=diversity,
        determinism=determinism,
        latency=latency,
        passed=passed,
    )


def load_quality_audit(path: Path = REPORT_PATH) -> QualityAuditReport:
    if not path.is_file():
        raise RuntimeError("quality audit report is missing")
    report = QualityAuditReport.model_validate_json(path.read_text(encoding="utf-8"))
    if report.engine_version != ENGINE_VERSION:
        raise RuntimeError("quality audit report does not match the active engine version")
    return report
