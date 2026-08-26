from typing import Literal

from pydantic import BaseModel, Field

from .event import InstrumentID
from .groove import GrooveIntent
from .meter import MeterDefinition
from .pattern import GroovePattern


class GenerateRequest(BaseModel):
    bpm: float = Field(100, ge=30, le=300)
    bars: int = Field(4, ge=1, le=64)
    meter: MeterDefinition = Field(default_factory=lambda: MeterDefinition.from_name("4/4"))
    intent: GrooveIntent = Field(default_factory=GrooveIntent)
    preset: str = "Balanced"
    seed: int = Field(42, ge=0)
    mode: Literal["preview", "high_quality"] = "preview"
    candidate_count: int = Field(4, ge=1, le=4)


class GenerateResponse(BaseModel):
    candidates: list[GroovePattern]


class MutateRequest(BaseModel):
    pattern: GroovePattern
    instruments: set[InstrumentID] = Field(default_factory=set)
    bars: set[int] = Field(default_factory=set)
    operation: str = "regenerate"


class PreferenceRequest(BaseModel):
    candidate_a: GroovePattern
    candidate_b: GroovePattern
    selected: Literal["A", "B"]
    display_order: list[str] = Field(default_factory=lambda: ["A", "B"])


class SavePresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    intent: GrooveIntent


class PresetsResponse(BaseModel):
    built_in: dict[str, GrooveIntent]
    user: dict[str, GrooveIntent]
