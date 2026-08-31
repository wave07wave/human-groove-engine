from pydantic import Field

from app.config import SCHEMA_VERSION

from .groove import UnitModel


class GroovePreferenceRange(UnitModel):
    mean: float = Field(ge=0, le=1)
    low: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    observations: int = Field(ge=0)
    evidence: float = Field(
        0,
        ge=0,
        le=1,
        description=(
            "Evidence that selected candidates were closer to this range than rejected ones"
        ),
    )


class GroovePreferenceSummary(UnitModel):
    comparisons: int = Field(ge=0)
    decisive_comparisons: int = Field(0, ge=0)
    ties: int = Field(0, ge=0)
    effective_comparisons: float = Field(0, ge=0)
    learning_confidence: float = Field(0, ge=0, le=1)
    personal_weight: float = Field(ge=0, le=0.8)
    feature_weights: dict[str, float] = Field(default_factory=dict)
    preferred_ranges: dict[str, GroovePreferenceRange] = Field(default_factory=dict)
    profile_scope: str | None = None
    schema_version: str = SCHEMA_VERSION
