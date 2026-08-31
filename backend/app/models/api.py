import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .event import InstrumentID
from .groove import GrooveIntent
from .meter import MeterDefinition
from .pattern import GroovePattern
from .preference import GroovePreferenceSummary


class GenerateRequest(BaseModel):
    bpm: float = Field(100, ge=30, le=300)
    bars: int = Field(4, ge=1, le=64)
    meter: MeterDefinition = Field(default_factory=lambda: MeterDefinition.from_name("4/4"))
    intent: GrooveIntent = Field(default_factory=GrooveIntent)
    preset: str = Field("Balanced", min_length=1, max_length=80)
    seed: int = Field(42, ge=0)
    mode: Literal["preview", "high_quality"] = "preview"
    performance_mode: Literal["auto", "rule"] = "auto"
    render_profile: Literal[
        "studio-tight-v1", "warm-pocket-v1", "club-punch-v1", "vintage-dust-v1", "off"
    ] = "studio-tight-v1"
    candidate_count: int = Field(4, ge=1, le=4)
    candidate_strategy: Literal["quality", "explore"] = "quality"
    anonymous_session_id: str | None = Field(
        default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9-]+$"
    )

    @field_validator("preset", mode="before")
    @classmethod
    def normalized_preset(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("preset must not be blank")
        return normalized


class GenerateResponse(BaseModel):
    candidates: list[GroovePattern]
    preference_profile: GroovePreferenceSummary | None = None


class MutateRequest(BaseModel):
    pattern: GroovePattern
    instruments: set[InstrumentID] = Field(default_factory=set)
    bars: set[int] = Field(default_factory=set)
    operation: str = "regenerate"


class PreferenceRequest(BaseModel):
    candidate_a: GroovePattern
    candidate_b: GroovePattern
    selected: Literal["A", "B", "tie"]
    display_order: list[str] = Field(default_factory=list, max_length=2)
    comparison_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9-]+$",
    )
    decision_time_ms: int | None = Field(default=None, ge=250, le=3_600_000)

    @model_validator(mode="after")
    def valid_comparison(self) -> "PreferenceRequest":
        candidate_ids = [self.candidate_a.pattern_id, self.candidate_b.pattern_id]
        if candidate_ids[0] == candidate_ids[1]:
            raise ValueError("preference candidates must be distinct")
        if not self.display_order:
            self.display_order = candidate_ids
        if len(self.display_order) != 2 or set(self.display_order) != set(candidate_ids):
            raise ValueError("display order must contain both candidate IDs exactly once")
        if self.candidate_a.metadata.style.strip() != self.candidate_b.metadata.style.strip():
            raise ValueError("preference candidates must use the same style")
        return self


class SavePresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    intent: GrooveIntent


class PresetsResponse(BaseModel):
    built_in: dict[str, GrooveIntent]
    user: dict[str, GrooveIntent]
