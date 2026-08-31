import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .api import GenerateRequest
from .pattern import GroovePattern

ParticipantGroup = Literal["producer", "drummer", "general", "undisclosed"]
BlindChoice = Literal["left", "right", "tie"]


class BlindSessionRequest(BaseModel):
    participant_group: ParticipantGroup = "undisclosed"
    consent: bool
    generation: GenerateRequest
    study_run_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9-]+$",
    )
    trial_index: int = Field(0, ge=0, le=5)

    @model_validator(mode="after")
    def require_consent(self) -> "BlindSessionRequest":
        if not self.consent:
            raise ValueError("consent is required before starting a listening evaluation")
        return self


class BlindCandidate(BaseModel):
    position: Literal["left", "right"]
    pattern: GroovePattern


class BlindSession(BaseModel):
    session_id: str
    participant_group: ParticipantGroup
    started_at: datetime
    study_run_id: str
    trial_index: int
    trials_in_block: int = 6
    candidates: list[BlindCandidate] = Field(min_length=2, max_length=2)
    instructions: str = (
        "Listen to both candidates through the same playback chain, then choose the "
        "groove you prefer. "
        "The performance conditions remain hidden until the response is submitted."
    )


class BlindResponseRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    selected: BlindChoice
    decision_time_ms: int = Field(ge=250, le=3_600_000)
    saved_choice: Literal["left", "right", "none"] = "none"

    @model_validator(mode="after")
    def saved_choice_matches_answer(self) -> "BlindResponseRequest":
        if self.saved_choice != "none" and self.saved_choice != self.selected:
            raise ValueError("saved choice must match the selected candidate")
        return self


class BlindResponseResult(BaseModel):
    accepted: bool = True
    selected_variant: Literal["learned", "rule", "tie"]
    left_variant: Literal["learned", "rule"]
    right_variant: Literal["learned", "rule"]


class EvaluationGroupSummary(BaseModel):
    participant_group: ParticipantGroup
    comparisons: int
    completed_blocks: int
    learned_wins: int
    rule_wins: int
    ties: int
    learned_win_rate: float
    confidence_low: float
    confidence_high: float
    median_decision_ms: int | None = None
    saved_rate: float


class EvaluationSummary(BaseModel):
    completed: int
    groups: list[EvaluationGroupSummary]
    minimum_blocks_per_declared_group: int = 20
    verdict: Literal["collecting", "inconclusive", "learned_supported", "rule_supported"]
    perceptual_claim_allowed: bool
    eligible_repeat_pairs: int
    repeat_consistency: float | None = None
    caveat: str


class TapObservation(BaseModel):
    phase_error: float | None = Field(default=None, ge=0, le=1)
    period_error: float | None = Field(default=None, ge=0, le=1)
    variability: float | None = Field(default=None, ge=0, le=1)


class MotionObservation(BaseModel):
    periodic_energy: float = Field(ge=0, le=1)
    movement_energy: float = Field(ge=0, le=1)
    device_quality: float = Field(ge=0, le=1)


class EmbodiedEvaluationRequest(BaseModel):
    anonymous_session_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9-]+$")
    pattern: GroovePattern
    urge_to_move: int = Field(ge=0, le=100)
    pleasure: int = Field(ge=0, le=100)
    beat_clarity: int = Field(ge=0, le=100)
    familiarity: int | None = Field(default=None, ge=0, le=100)
    style_liking: int | None = Field(default=None, ge=0, le=100)
    tap_observation: TapObservation | None = None
    motion_observation: MotionObservation | None = None
    listening_context: Literal["unknown", "headphones", "speakers"] = "unknown"
    posture: Literal["unknown", "seated", "standing"] = "unknown"
    motion_consent: bool = False

    @model_validator(mode="after")
    def motion_requires_consent(self) -> "EmbodiedEvaluationRequest":
        if self.motion_observation is not None and not self.motion_consent:
            raise ValueError("motion consent is required when motion data is submitted")
        return self


class EmbodiedEvaluationResult(BaseModel):
    accepted: bool = True
    evidence_class: Literal["self_report", "tap", "motion"]
    caveat: str = (
        "Stored as optional evaluation evidence, not as proof that the pattern makes people dance."
    )


class EmbodiedOperatorSummary(BaseModel):
    operator_arm: str
    evaluations: int = Field(ge=0)
    average_urge_to_move: float = Field(ge=0, le=100)
    average_pleasure: float = Field(ge=0, le=100)
    average_beat_clarity: float = Field(ge=0, le=100)


class EmbodiedEvaluationSummary(BaseModel):
    total_evaluations: int = Field(ge=0)
    operator_arms: list[EmbodiedOperatorSummary]
    minimum_evaluations_per_arm: int = 8
    sufficient_for_personal_comparison: bool = False
    caveat: str = (
        "Personal, optional self-report summary. It is not evidence of a general dance effect."
    )


class MotorTempoCalibrationRequest(BaseModel):
    anonymous_session_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9-]+$")
    timestamps_ms: list[float] = Field(min_length=12, max_length=40)

    @model_validator(mode="after")
    def timestamps_are_valid(self) -> "MotorTempoCalibrationRequest":
        if any(
            not isinstance(value, (float, int)) or value != value for value in self.timestamps_ms
        ):
            raise ValueError("tap timestamps must be finite")
        if any(right <= left for left, right in zip(self.timestamps_ms, self.timestamps_ms[1:])):
            raise ValueError("tap timestamps must be strictly increasing")
        return self


class MotorTempoProfile(BaseModel):
    bpm: float = Field(ge=30, le=300)
    interval_ms: float = Field(ge=200, le=2000)
    dispersion: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    tempo_aliases: list[float]
    accepted_taps: int = Field(ge=9)
    caveat: str = "Optional comfortable-tap estimate; it does not replace your chosen BPM."
