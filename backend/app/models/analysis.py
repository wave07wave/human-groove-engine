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


class MetricLevelAnalysis(BaseModel):
    clarity: float = Field(ge=0, le=1)
    phase_stability: float = Field(ge=0, le=1)
    activity: float = Field(ge=0, le=1)


class MotorScaffoldAnalysis(BaseModel):
    subdivision: MetricLevelAnalysis
    tactus: MetricLevelAnalysis
    half_time: MetricLevelAnalysis
    bar_cycle: MetricLevelAnalysis


class PredictionErrorAnalysis(BaseModel):
    event_surprise: float = Field(ge=0, le=1)
    omission_surprise: float = Field(ge=0, le=1)
    concentration: float = Field(ge=0, le=1)
    recoverable_ratio: float = Field(ge=0, le=1)
    context_confidence: float = Field(ge=0, le=1)


class TimingCoherenceAnalysis(BaseModel):
    lane_offsets_ms: dict[str, float] = Field(default_factory=dict)
    within_lane_dispersion: float = Field(ge=0, le=1)
    pairwise_phase_coherence: float = Field(ge=0, le=1)
    shared_drift: float = Field(ge=0, le=1)
    independent_jitter: float = Field(ge=0, le=1)
    coherence: float = Field(ge=0, le=1)


class LowEndMotionAnalysis(BaseModel):
    symbolic_coupling: float = Field(ge=0, le=1)
    spectral_flux_50_100hz: float | None = Field(default=None, ge=0, le=1)
    onset_coherence: float | None = Field(default=None, ge=0, le=1)
    envelope_cycle: float | None = Field(default=None, ge=0, le=1)
    render_applicable: bool = False


class PhraseRenewalAnalysis(BaseModel):
    motif_memory: float = Field(ge=0, le=1)
    layer_entry_lift: float = Field(ge=0, le=1)
    challenge_strength: float = Field(ge=0, le=1)
    reentry_strength: float = Field(ge=0, le=1)


class EmbodiedEstimates(BaseModel):
    urge_to_move_prior: float = Field(ge=0, le=1)
    pleasure_prior: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    caveat: str = "Research heuristic; not a measurement of a person's body or emotion."


class EmbodiedGrooveFeatures(BaseModel):
    schema_version: str = "1.0"
    motor_scaffold: MotorScaffoldAnalysis
    prediction_error: PredictionErrorAnalysis
    timing_coherence: TimingCoherenceAnalysis
    low_end_motion: LowEndMotionAnalysis
    phrase_renewal: PhraseRenewalAnalysis
    estimates: EmbodiedEstimates


class AnalysisConfidence(BaseModel):
    overall: float = Field(0.72, ge=0, le=1)
    caveat: str = "Heuristic prediction, not a physiological measurement."


class RenderedAudioAnalysis(BaseModel):
    scope: str = "groove"
    profile_id: str
    profile_version: str
    sample_rate: int = Field(ge=8_000)
    analyzed_bars: list[int]
    rendered_events: int = Field(ge=0)
    low_end_collision: float = Field(ge=0, le=1)
    low_end_collision_applicable: bool
    transient_masking: float = Field(ge=0, le=1)
    onset_clarity: float = Field(ge=0, le=1)
    headroom: float = Field(ge=0, le=1)
    render_quality: float = Field(ge=0, le=1)
    low_frequency_flux: float | None = Field(default=None, ge=0, le=1)
    kick_bass_onset_coherence: float | None = Field(default=None, ge=0, le=1)
    low_end_envelope_cycle: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    caveat: str


class GrooveAnalysis(BaseModel):
    measured_dna: GrooveDNA
    listener: ListenerAnalysis
    confidence: AnalysisConfidence = Field(default_factory=AnalysisConfidence)
    intent_loss: float = Field(default=0, ge=0)
    fitness: float = 0
    rendered_audio: RenderedAudioAnalysis | None = None
    embodied: EmbodiedGrooveFeatures | None = None
