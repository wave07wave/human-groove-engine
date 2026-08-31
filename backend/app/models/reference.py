from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator

from .groove import GrooveDNA, GrooveIntent
from .meter import MeterDefinition


class TapAnalyzeRequest(BaseModel):
    timestamps_ms: list[float] = Field(min_length=3, max_length=64)
    current_intent: GrooveIntent = Field(default_factory=GrooveIntent)

    @field_validator("timestamps_ms")
    @classmethod
    def increasing_finite_timestamps(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(value) for value in values):
            raise ValueError("tap timestamps must be finite")
        if any(right <= left for left, right in zip(values, values[1:])):
            raise ValueError("tap timestamps must be strictly increasing")
        return values


class TapAnalysis(BaseModel):
    bpm: float = Field(ge=30, le=300)
    timing_stability: float = Field(ge=0, le=1)
    alternating_feel: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    accepted_taps: int = Field(ge=3)
    suggested_intent: GrooveIntent


class MidiReferenceRequest(BaseModel):
    filename: str = Field(default="reference.mid", max_length=200)
    midi_base64: str = Field(min_length=4, max_length=3_000_000)
    current_intent: GrooveIntent = Field(default_factory=GrooveIntent)


class MidiReferenceAnalysis(BaseModel):
    filename: str
    bpm: float = Field(ge=30, le=300)
    meter: MeterDefinition
    bars: int = Field(ge=1, le=64)
    hit_count: int = Field(ge=1)
    measured_dna: GrooveDNA
    suggested_intent: GrooveIntent
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class IntentTransformRequest(BaseModel):
    text: str = Field(min_length=1, max_length=240)
    current_intent: GrooveIntent = Field(default_factory=GrooveIntent)


class IntentChange(BaseModel):
    dimension: str
    before: float | str
    after: float | str
    reason: str


class IntentTransformResponse(BaseModel):
    intent: GrooveIntent
    suggested_style: str | None = None
    changes: list[IntentChange] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    message: str
