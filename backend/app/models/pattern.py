from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import (
    ANALYSIS_VERSION,
    ENGINE_VERSION,
    PRESET_VERSION,
    RNG_ALGORITHM,
    SCHEMA_VERSION,
)

from .analysis import GrooveAnalysis
from .event import GrooveEvent, InstrumentID
from .groove import GrooveIntent
from .meter import MeterDefinition


class PatternMetadata(BaseModel):
    engine_version: str = ENGINE_VERSION
    analysis_version: str = ANALYSIS_VERSION
    schema_version: str = SCHEMA_VERSION
    preset_version: str = PRESET_VERSION
    rng_algorithm: str = RNG_ALGORITHM
    master_seed: int
    style: str = Field("Balanced", min_length=1, max_length=80)
    performance_model: str = "rule-pocket-v1"
    performance_model_version: str = "1.0.0"
    render_profile: str = "studio-tight-v1"
    preference_guided: bool = False
    preference_guidance_strength: float = Field(0, ge=0, le=0.35)
    preference_guided_features: list[str] = Field(default_factory=list)
    embodied_operator_arm: str = "baseline"
    knowledge_pack_id: str = "neutral-v1"
    knowledge_pack_version: str = "1.0"

    @field_validator("style", mode="before")
    @classmethod
    def normalized_style(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("style must not be blank")
        return normalized


class GroovePattern(BaseModel):
    pattern_id: str
    name: str = "Untitled Groove"
    bpm: float = Field(ge=30, le=300)
    bars: int = Field(ge=1, le=64)
    meter: MeterDefinition
    events: list[GrooveEvent]
    intent: GrooveIntent
    metadata: PatternMetadata
    analysis: GrooveAnalysis | None = None
    instrument_locks: set[InstrumentID] = Field(default_factory=set)
    bar_locks: set[int] = Field(default_factory=set)

    @model_validator(mode="after")
    def events_within_phrase(self) -> "GroovePattern":
        end = self.bars * self.meter.bar_ticks
        if any(e.grid_tick >= end for e in self.events):
            raise ValueError("event outside phrase")
        return self
