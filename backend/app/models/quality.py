from pydantic import BaseModel, Field


class ControlResponseAudit(BaseModel):
    dimension: str
    low_mean: float
    high_mean: float
    delta: float
    minimum_delta: float
    passed: bool


class DiversityAudit(BaseModel):
    comparisons: int
    mean_distance: float
    minimum_distance: float
    required_mean_distance: float
    required_minimum_distance: float
    passed: bool


class DeterminismAudit(BaseModel):
    cases: int
    mismatches: int
    passed: bool


class LatencyAudit(BaseModel):
    samples: int
    median_seconds: float
    p95_seconds: float
    maximum_p95_seconds: float
    passed: bool


class QualityAuditReport(BaseModel):
    audit_version: str = "engine-quality-v1"
    engine_version: str
    generated_at: str
    runtime: str
    control_seed_count: int
    controls: list[ControlResponseAudit] = Field(min_length=1)
    diversity: DiversityAudit
    determinism: DeterminismAudit
    latency: LatencyAudit
    passed: bool
    perceptual_quality_claim: bool = False
    caveat: str = (
        "Technical regression audit only. Passing does not establish that listeners "
        "prefer the output."
    )
