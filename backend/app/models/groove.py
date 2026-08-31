from pydantic import BaseModel, ConfigDict, Field, field_validator


class UnitModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class GrooveDNA(UnitModel):
    pulse_stability: float = Field(0.75, ge=0, le=1)
    beat_salience: float = Field(0.75, ge=0, le=1)
    syncopation: float = Field(0.45, ge=0, le=1)
    anticipation: float = Field(0.35, ge=0, le=1)
    omission: float = Field(0.2, ge=0, le=1)
    density: float = Field(0.5, ge=0, le=1)
    repetition: float = Field(0.65, ge=0, le=1)
    variation: float = Field(0.35, ge=0, le=1)
    interlock: float = Field(0.6, ge=0, le=1)
    swing: float = Field(0.15, ge=0, le=1)
    microtiming: float = Field(0.3, ge=0, le=1)
    velocity_contrast: float = Field(0.45, ge=0, le=1)
    duration_contrast: float = Field(0.3, ge=0, le=1)
    low_end_anchor: float = Field(0.7, ge=0, le=1)
    metric_ambiguity: float = Field(0.2, ge=0, le=1)
    ghost_density: float = Field(0.25, ge=0, le=1)
    surprise: float = Field(0.35, ge=0, le=1)
    recovery_strength: float = Field(0.7, ge=0, le=1)
    motor_affordance: float = Field(0.75, ge=0, le=1)
    hypnotic: float = Field(0.35, ge=0, le=1)
    phrase_development: float = Field(0.4, ge=0, le=1)


class GrooveTolerance(UnitModel):
    default: float = Field(0.12, ge=0, le=1)
    per_dimension: dict[str, float] = Field(default_factory=dict)


class GroovePriority(UnitModel):
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "pulse_stability": 1.2,
            "syncopation": 1.0,
            "density": 0.8,
            "variation": 0.7,
            "interlock": 1.0,
            "surprise": 0.8,
        }
    )


class EmbodiedIntent(UnitModel):
    """Optional, explainable controls for the embodied groove research layer."""

    challenge: float = Field(0.0, ge=0, le=1)
    renewal: float = Field(0.0, ge=0, le=1)
    timing_coherence: float = Field(0.7, ge=0, le=1)
    low_end_motion: float = Field(0.6, ge=0, le=1)
    meter_familiarity: float = Field(0.5, ge=0, le=1)
    style_familiarity: float = Field(0.5, ge=0, le=1)


class GrooveIntent(BaseModel):
    target_dna: GrooveDNA = Field(default_factory=GrooveDNA)
    tolerance: GrooveTolerance = Field(default_factory=GrooveTolerance)
    priorities: GroovePriority = Field(default_factory=GroovePriority)
    movement_target: str = "bounce"
    phrase_energy_curve: list[float] = Field(default_factory=list, max_length=64)
    embodied: EmbodiedIntent = Field(default_factory=EmbodiedIntent)

    @field_validator("phrase_energy_curve")
    @classmethod
    def valid_energy_curve(cls, values: list[float]) -> list[float]:
        if values and len(values) < 2:
            raise ValueError("phrase energy curve requires at least two points")
        if any(not 0 <= value <= 1 for value in values):
            raise ValueError("phrase energy values must be between zero and one")
        return values


class ComplexityVector(UnitModel):
    micro: float = Field(0.2, ge=0, le=1)
    subdivision: float = Field(0.5, ge=0, le=1)
    beat: float = Field(0.3, ge=0, le=1)
    bar: float = Field(0.35, ge=0, le=1)
    phrase: float = Field(0.4, ge=0, le=1)
