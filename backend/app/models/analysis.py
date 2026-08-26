from pydantic import BaseModel, Field

from .groove import GrooveDNA


class ListenerAnalysis(BaseModel):
    predicted_groove: float = Field(ge=0, le=1)
    beat_confidence: float = Field(ge=0, le=1)
    meter_confidence: float = Field(ge=0, le=1)
    movement_proxy: float = Field(ge=0, le=1)
    pleasure_proxy: float = Field(ge=0, le=1)
    surprise: float = Field(ge=0, le=1)
    resolvable_surprise: float = Field(ge=0, le=1)
    learning_progress: float = Field(ge=-1, le=1)
    boredom: float = Field(ge=0, le=1)
    confusion: float = Field(ge=0, le=1)
    irritation: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class AnalysisConfidence(BaseModel):
    overall: float = Field(0.72, ge=0, le=1)
    caveat: str = "Heuristic prediction, not a physiological measurement."


class GrooveAnalysis(BaseModel):
    measured_dna: GrooveDNA
    listener: ListenerAnalysis
    confidence: AnalysisConfidence = Field(default_factory=AnalysisConfidence)
    intent_loss: float = Field(default=0, ge=0)
    fitness: float = 0
