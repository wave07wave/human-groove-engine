from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import (
    ANALYSIS_VERSION,
    ENGINE_VERSION,
    PRESET_VERSION,
    RNG_ALGORITHM,
    SCHEMA_VERSION,
)
from app.models.meter import MeterDefinition


class UnitModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class SpelledPitchClass(UnitModel):
    letter: str = Field(pattern=r"^[A-G]$")
    accidental: int = Field(default=0, ge=-2, le=2)
    pitch_class: int = Field(ge=0, le=11)


class ChordQuality(StrEnum):
    MAJOR = "major"
    MINOR = "minor"
    MAJOR7 = "major7"
    DOMINANT7 = "dominant7"
    MINOR7 = "minor7"
    MINOR7B5 = "minor7b5"
    DIM = "dim"
    DIM7 = "dim7"
    AUG = "aug"
    SUS2 = "sus2"
    SUS4 = "sus4"
    SIX = "6"
    MINOR6 = "minor6"
    ADD9 = "add9"
    NINE = "9"
    ELEVEN = "11"
    THIRTEEN = "13"


class ScaleMode(StrEnum):
    MAJOR = "major"
    NATURAL_MINOR = "natural_minor"
    HARMONIC_MINOR = "harmonic_minor"
    MELODIC_MINOR = "melodic_minor"
    DORIAN = "dorian"
    PHRYGIAN = "phrygian"
    LYDIAN = "lydian"
    MIXOLYDIAN = "mixolydian"
    AEOLIAN = "aeolian"
    LOCRIAN = "locrian"
    MAJOR_PENTATONIC = "major_pentatonic"
    MINOR_PENTATONIC = "minor_pentatonic"
    BLUES = "blues"
    CHROMATIC = "chromatic"


class KeyContext(UnitModel):
    tonic: SpelledPitchClass
    mode: ScaleMode = ScaleMode.MAJOR


class Chord(UnitModel):
    root: SpelledPitchClass
    quality: ChordQuality
    spelled_tones: list[SpelledPitchClass]
    pitch_classes: set[int]
    extensions: list[int] = Field(default_factory=list)
    alterations: list[str] = Field(default_factory=list)
    bass_note: SpelledPitchClass | None = None


class HarmonyEvent(UnitModel):
    start_tick: int = Field(ge=0)
    duration_tick: int = Field(gt=0)
    chord: Chord | None = None
    key_context: KeyContext | None = None


class HarmonyTimeline(UnitModel):
    events: list[HarmonyEvent]

    @model_validator(mode="after")
    def ordered_non_overlapping(self) -> "HarmonyTimeline":
        ordered = sorted(self.events, key=lambda event: event.start_tick)
        for left, right in zip(ordered, ordered[1:]):
            if left.start_tick + left.duration_tick > right.start_tick:
                raise ValueError("harmony events cannot overlap")
        object.__setattr__(self, "events", ordered)
        return self


class TempoSegment(UnitModel):
    start_tick: int = Field(default=0, ge=0)
    bpm: float = Field(default=100, ge=30, le=300)


class TempoMap(UnitModel):
    segments: list[TempoSegment] = Field(default_factory=lambda: [TempoSegment()])

    @model_validator(mode="after")
    def starts_at_zero(self) -> "TempoMap":
        object.__setattr__(
            self, "segments", sorted(self.segments, key=lambda item: item.start_tick)
        )
        if not self.segments or self.segments[0].start_tick != 0:
            raise ValueError("tempo map must start at tick zero")
        return self


class HarmonicRole(StrEnum):
    STRUCTURAL_ROOT = "structural_root"
    ROOT = "root"
    THIRD = "third"
    FIFTH = "fifth"
    SEVENTH = "seventh"
    EXTENSION = "extension"
    SCALE_TONE = "scale_tone"
    PASSING = "passing"
    APPROACH = "approach"
    CHROMATIC_APPROACH = "chromatic_approach"
    ENCLOSURE = "enclosure"
    NEIGHBOR = "neighbor"
    PEDAL = "pedal"
    ANTICIPATION = "anticipation"
    TARGET = "target"


class RhythmicRole(StrEnum):
    ANCHOR = "anchor"
    CONFIRMATION = "confirmation"
    ANTICIPATION = "anticipation"
    VIOLATION = "violation"
    RECOVERY = "recovery"
    GHOST = "ghost"
    DECORATION = "decoration"
    TRANSITION = "transition"


class StructuralRole(StrEnum):
    EXPECTED_OMISSION = "expected_omission"
    INTENTIONAL_GAP = "intentional_gap"
    KICK_EXPOSURE = "kick_exposure"
    PRE_RESOLUTION_GAP = "pre_resolution_gap"
    PHRASE_BREAK = "phrase_break"
    RECOVERY_TARGET = "recovery_target"


class ConnectionType(StrEnum):
    NORMAL = "normal"
    STACCATO = "staccato"
    LEGATO = "legato"
    TENUTO = "tenuto"


class TechniqueType(StrEnum):
    NORMAL = "normal"
    MUTE = "mute"
    GHOST = "ghost"
    SLIDE_HINT = "slide_hint"
    HAMMER_HINT = "hammer_hint"
    PULL_HINT = "pull_hint"


class AccentType(StrEnum):
    NORMAL = "normal"
    ACCENT = "accent"
    SOFT = "soft"


class BassVoicePolicy(StrEnum):
    MONOPHONIC_RETRIGGER = "monophonic_retrigger"
    MONOPHONIC_LEGATO = "monophonic_legato"
    ALLOW_OVERLAP = "allow_overlap"


class BassArticulation(UnitModel):
    connection: ConnectionType = ConnectionType.NORMAL
    technique: TechniqueType = TechniqueType.NORMAL
    accent: AccentType = AccentType.NORMAL
    legato_overlap_tick: int = Field(default=0, ge=0)


class EventLocks(UnitModel):
    timing: bool = False
    pitch: bool = False
    duration: bool = False
    velocity: bool = False
    articulation: bool = False


class EventProvenance(UnitModel):
    origin: str = "generated"
    generator_stage: str | None = None
    mutation_operation: str | None = None
    parent_motif_id: str | None = None


class BassDecisionTrace(UnitModel):
    onset_reason: str
    pitch_reason: str
    duration_reason: str
    octave_reason: str
    articulation_reason: str
    kick_relationship: str
    target_event_id: str | None = None
    target_pitch: int | None = Field(default=None, ge=0, le=127)
    factors: dict[str, float] = Field(default_factory=dict)


class BassEvent(UnitModel):
    event_id: str
    grid_tick: int = Field(ge=0)
    structural_offset_tick: int = 0
    micro_offset_us: int = Field(default=0, ge=-25_000, le=25_000)
    duration_tick: int = Field(gt=0)
    pitch: int = Field(ge=0, le=127)
    velocity: int = Field(ge=1, le=127)
    harmonic_role: HarmonicRole
    rhythmic_role: RhythmicRole
    articulation: BassArticulation = Field(default_factory=BassArticulation)
    structural_weight: float = Field(default=0.5, ge=0, le=1)
    phrase_id: str
    motif_id: str | None = None
    approach_target_id: str | None = None
    locks: EventLocks = Field(default_factory=EventLocks)
    provenance: EventProvenance = Field(default_factory=EventProvenance)
    decision_trace: BassDecisionTrace | None = None

    @model_validator(mode="after")
    def nonnegative_performed_time(self) -> "BassEvent":
        if self.grid_tick + self.structural_offset_tick < 0:
            raise ValueError("performed tick cannot be negative")
        if self.harmonic_role in (HarmonicRole.APPROACH, HarmonicRole.CHROMATIC_APPROACH):
            if not self.approach_target_id:
                raise ValueError("approach events require approach_target_id")
        return self

    @property
    def performed_tick(self) -> int:
        return max(0, self.grid_tick + self.structural_offset_tick)


class BassStructuralEvent(UnitModel):
    event_id: str
    start_tick: int = Field(ge=0)
    duration_tick: int = Field(gt=0)
    role: StructuralRole
    target_event_id: str | None = None
    strength: float = Field(default=0.5, ge=0, le=1)


class BassIntentDNA(UnitModel):
    root_strength: float = Field(0.72, ge=0, le=1)
    chord_tone_strength: float = Field(0.78, ge=0, le=1)
    chromaticism: float = Field(0.16, ge=0, le=1)
    approach_activity: float = Field(0.28, ge=0, le=1)
    melodic_motion: float = Field(0.42, ge=0, le=1)
    stepwise_motion: float = Field(0.68, ge=0, le=1)
    leap_activity: float = Field(0.18, ge=0, le=1)
    register_motion: float = Field(0.28, ge=0, le=1)
    syncopation: float = Field(0.34, ge=0, le=1)
    kick_lock: float = Field(0.58, ge=0, le=1)
    kick_complement: float = Field(0.35, ge=0, le=1)
    kick_answer: float = Field(0.25, ge=0, le=1)
    density: float = Field(0.46, ge=0, le=1)
    silence: float = Field(0.30, ge=0, le=1)
    duration_contrast: float = Field(0.35, ge=0, le=1)
    velocity_contrast: float = Field(0.32, ge=0, le=1)
    repetition: float = Field(0.64, ge=0, le=1)
    variation: float = Field(0.36, ge=0, le=1)
    phrase_development: float = Field(0.42, ge=0, le=1)
    tension: float = Field(0.32, ge=0, le=1)
    resolution_strength: float = Field(0.72, ge=0, le=1)
    human_feel: float = Field(0.34, ge=0, le=1)


class BassTolerance(UnitModel):
    default: float = Field(0.14, ge=0, le=1)
    per_dimension: dict[str, float] = Field(default_factory=dict)


class BassPriority(UnitModel):
    rhythm: float = Field(1.0, ge=0)
    harmony: float = Field(1.1, ge=0)
    melody: float = Field(0.8, ge=0)
    kick_relation: float = Field(0.9, ge=0)
    articulation: float = Field(0.5, ge=0)
    phrase: float = Field(0.8, ge=0)


class BassIntent(UnitModel):
    target: BassIntentDNA = Field(default_factory=BassIntentDNA)
    tolerances: BassTolerance = Field(default_factory=BassTolerance)
    priorities: BassPriority = Field(default_factory=BassPriority)
    allow_chromatic_notes: bool = True


class AtomicBassFeatures(UnitModel):
    root_ratio: float = 0
    structural_root_ratio: float = 0
    chord_tone_ratio: float = 0
    scale_tone_ratio: float = 0
    chromatic_ratio: float = 0
    resolved_chromatic_ratio: float = 0
    approach_ratio: float = 0
    passing_ratio: float = 0
    onset_density: float = 0
    active_occupancy: float = 0
    silence_ratio: float = 1
    syncopation_index: float = 0
    anticipation_ratio: float = 0
    mean_interval: float = 0
    step_ratio: float = 0
    leap_ratio: float = 0
    octave_ratio: float = 0
    register_mean: float = 0
    register_span: float = 0
    register_variance: float = 0
    duration_variance: float = 0
    velocity_variance: float = 0
    kick_lock_ratio: float | None = None
    kick_complement_score: float | None = None
    kick_answer_score: float | None = None
    motif_similarity: float = 0
    repetition_score: float = 0


class DerivedBassDNA(UnitModel):
    harmonic_stability: float = 0
    melodic_motion: float = 0
    pulse_support: float = 0
    low_end_anchor: float = 0
    kick_relationship_quality: float | None = None
    motor_affordance: float = 0
    phrase_development: float = 0
    motif_identity: float = 0
    tension: float = 0
    resolution_strength: float = 0
    timing_character_strength: float = 0


class MetricResult(UnitModel):
    value: float | None
    confidence: float = Field(ge=0, le=1)
    applicable: bool = True


class BassListenerAnalysis(UnitModel):
    rhythmic_coherence: MetricResult
    harmonic_coherence: MetricResult
    pitch_motion_quality: MetricResult
    voice_leading_quality: MetricResult
    phrase_coherence: MetricResult
    motif_identity: MetricResult
    kick_bass_quality: MetricResult
    pulse_support: MetricResult
    motor_affordance: MetricResult
    resolvable_tension: MetricResult
    learning_progress: MetricResult
    boredom: MetricResult
    confusion: MetricResult
    overactivity: MetricResult
    novelty: MetricResult
    predicted_bass_groove: MetricResult
    musical_interest: MetricResult


class BassAnalysis(UnitModel):
    atomic: AtomicBassFeatures
    dna: DerivedBassDNA
    listener: BassListenerAnalysis
    intent_loss: float = Field(ge=0)
    fitness: float


class RegisterLimits(UnitModel):
    lowest_midi_note: int = Field(28, ge=0, le=127)
    highest_midi_note: int = Field(60, ge=0, le=127)
    preferred_center: float = Field(42, ge=0, le=127)
    preferred_zone: str = "core"
    max_single_leap: int = Field(12, ge=1, le=36)

    @model_validator(mode="after")
    def valid_range(self) -> "RegisterLimits":
        if self.lowest_midi_note >= self.highest_midi_note:
            raise ValueError("lowest_midi_note must be below highest_midi_note")
        if not self.lowest_midi_note <= self.preferred_center <= self.highest_midi_note:
            raise ValueError("preferred_center must be within register limits")
        return self


class BassPatternMetadata(UnitModel):
    engine_version: str = ENGINE_VERSION
    schema_version: str = SCHEMA_VERSION
    analysis_version: str = ANALYSIS_VERSION
    preset_version: str = PRESET_VERSION
    rng_algorithm: str = RNG_ALGORITHM
    master_seed: int
    preset: str = Field("Supportive", min_length=1, max_length=80)
    candidate_index: int = 0
    revision: int = 0
    resolved_intent_notes: list[str] = Field(default_factory=list)
    preference_guided: bool = False
    preference_guidance_strength: float = Field(0, ge=0, le=0.35)
    preference_guided_features: list[str] = Field(default_factory=list)

    @field_validator("preset", mode="before")
    @classmethod
    def normalized_preset(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("preset must not be blank")
        return normalized


class KickEvent(UnitModel):
    grid_tick: int = Field(ge=0)
    structural_offset_tick: int = 0
    micro_offset_us: int = Field(default=0, ge=-25_000, le=25_000)
    velocity: int = Field(default=100, ge=1, le=127)

    @property
    def performed_tick(self) -> int:
        return max(0, self.grid_tick + self.structural_offset_tick)


class GrooveContext(UnitModel):
    tempo_map: TempoMap
    meter: MeterDefinition
    phrase_boundaries: list[int] = Field(default_factory=list)
    beat_map: list[float] = Field(default_factory=list)
    metric_gravity: list[float] = Field(default_factory=list)
    tension_curve: list[float] = Field(default_factory=list)
    kick_events: list[KickEvent] = Field(default_factory=list)
    groove_dna: dict[str, float] = Field(default_factory=dict)


class RhythmBassInteractionDNA(UnitModel):
    kick_bass_lock: float
    kick_bass_complement: float
    kick_bass_answer: float
    kick_bass_anticipation: float
    perceived_phase_coherence: float
    low_end_complexity_balance: float
    shared_tension: float
    shared_recovery: float
    low_end_space: float
    pulse_reinforcement: float


class BassIntentLocks(UnitModel):
    keep_rhythm_feel: bool = False
    keep_register: bool = False
    keep_kick_relationship: bool = False


class InputMode(StrEnum):
    CHORD_PROGRESSION = "chord_progression"
    KEY_MODE = "key_mode"
    ROOT_GUIDE = "root_guide"
    NO_HARMONY = "no_harmony"


class BassPattern(UnitModel):
    pattern_id: str
    name: str = "Generated Bass"
    bpm: float = Field(100, ge=30, le=300)
    bars: int = Field(ge=1, le=64)
    meter: MeterDefinition
    tempo_map: TempoMap
    harmony: HarmonyTimeline
    key_context: KeyContext | None = None
    input_mode: InputMode = InputMode.CHORD_PROGRESSION
    events: list[BassEvent]
    structural_events: list[BassStructuralEvent] = Field(default_factory=list)
    intent: BassIntent
    intent_locks: BassIntentLocks = Field(default_factory=BassIntentLocks)
    register_limits: RegisterLimits = Field(default_factory=RegisterLimits)
    voice_policy: BassVoicePolicy = BassVoicePolicy.MONOPHONIC_RETRIGGER
    metadata: BassPatternMetadata
    analysis: BassAnalysis | None = None
    groove_context: GrooveContext | None = None
    interaction_analysis: RhythmBassInteractionDNA | None = None

    @model_validator(mode="after")
    def structural_integrity(self) -> "BassPattern":
        end_tick = self.bars * self.meter.bar_ticks
        ids = {event.event_id for event in self.events}
        if len(ids) != len(self.events):
            raise ValueError("event IDs must be unique")
        if any(event.grid_tick >= end_tick for event in self.events):
            raise ValueError("bass event outside pattern")
        if any(event.performed_tick >= end_tick for event in self.events):
            raise ValueError("performed bass event outside pattern")
        if any(event.grid_tick + event.duration_tick > end_tick for event in self.events):
            raise ValueError("bass event duration exceeds pattern")
        if any(
            event.approach_target_id and event.approach_target_id not in ids
            for event in self.events
        ):
            raise ValueError("approach target must reference an event in the pattern")
        structural_ids = {event.event_id for event in self.structural_events}
        if len(structural_ids) != len(self.structural_events):
            raise ValueError("structural event IDs must be unique")
        if any(
            event.start_tick + event.duration_tick > end_tick
            for event in self.structural_events
        ):
            raise ValueError("structural event outside pattern")
        if any(
            event.target_event_id and event.target_event_id not in ids
            for event in self.structural_events
        ):
            raise ValueError("structural target must reference an event in the pattern")
        object.__setattr__(
            self,
            "events",
            sorted(self.events, key=lambda event: (event.performed_tick, event.event_id)),
        )
        return self

class BassGenerateRequest(UnitModel):
    bpm: float = Field(100, ge=30, le=300)
    bars: int = Field(4, ge=1, le=64)
    meter: MeterDefinition = Field(default_factory=lambda: MeterDefinition.from_name("4/4"))
    input_mode: InputMode = InputMode.CHORD_PROGRESSION
    harmony: str = "Cmaj7"
    key: str | None = "C"
    mode: ScaleMode = ScaleMode.MAJOR
    intent: BassIntent = Field(default_factory=BassIntent)
    preset: str = Field("Supportive", min_length=1, max_length=80)
    seed: int = Field(42, ge=0)
    candidate_count: int = Field(4, ge=1, le=4)
    register_limits: RegisterLimits = Field(default_factory=RegisterLimits)
    voice_policy: BassVoicePolicy = BassVoicePolicy.MONOPHONIC_RETRIGGER
    groove_context: GrooveContext | None = None

    @field_validator("preset", mode="before")
    @classmethod
    def normalized_preset(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("preset must not be blank")
        return normalized


class BassGenerateResponse(UnitModel):
    candidates: list[BassPattern]
    preference_profile: "BassPreferenceSummary | None" = None


class MutationOperation(StrEnum):
    RHYTHM_ONLY = "rhythm_only"
    PITCH_ONLY = "pitch_only"
    TIMING_ONLY = "timing_only"
    ARTICULATION_ONLY = "articulation_only"
    DURATION_ONLY = "duration_only"
    REGENERATE = "regenerate"


class BassPreserveOptions(UnitModel):
    keep_rhythm: bool = False
    keep_pitch: bool = False
    keep_duration: bool = False
    keep_timing: bool = False
    keep_motif: bool = False
    keep_kick_relation: bool = False
    keep_register_shape: bool = False


class BassMutateRequest(UnitModel):
    pattern: BassPattern
    bars: set[int] = Field(default_factory=set)
    operation: MutationOperation = MutationOperation.REGENERATE
    preserve: BassPreserveOptions = Field(default_factory=BassPreserveOptions)


class BassRefineRequest(UnitModel):
    pattern: BassPattern
    strength: float = Field(0.35, ge=0, le=1)


class SaveBassPresetRequest(UnitModel):
    name: str = Field(min_length=1, max_length=80)
    intent: BassIntent


class BassPreferenceRequest(UnitModel):
    candidate_a: BassPattern
    candidate_b: BassPattern
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
    def valid_comparison(self) -> "BassPreferenceRequest":
        candidate_ids = [self.candidate_a.pattern_id, self.candidate_b.pattern_id]
        if candidate_ids[0] == candidate_ids[1]:
            raise ValueError("preference candidates must be distinct")
        if not self.display_order:
            self.display_order = candidate_ids
        if len(self.display_order) != 2 or set(self.display_order) != set(candidate_ids):
            raise ValueError("display order must contain both candidate IDs exactly once")
        if self.candidate_a.metadata.preset.strip() != self.candidate_b.metadata.preset.strip():
            raise ValueError("preference candidates must use the same preset")
        return self


class PreferenceRange(UnitModel):
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


class BassPreferenceSummary(UnitModel):
    comparisons: int = Field(ge=0)
    decisive_comparisons: int = Field(0, ge=0)
    ties: int = Field(0, ge=0)
    effective_comparisons: float = Field(0, ge=0)
    learning_confidence: float = Field(0, ge=0, le=1)
    personal_weight: float = Field(ge=0, le=0.8)
    feature_weights: dict[str, float] = Field(default_factory=dict)
    preferred_ranges: dict[str, PreferenceRange] = Field(default_factory=dict)
    profile_scope: str | None = None
    schema_version: str = SCHEMA_VERSION


class BassPatternExchange(UnitModel):
    kind: Literal["human_bass_pattern"] = "human_bass_pattern"
    schema_version: Literal["1.0"] = "1.0"
    pattern: BassPattern


class BassIntentExchange(UnitModel):
    kind: Literal["human_bass_intent"] = "human_bass_intent"
    schema_version: Literal["1.0"] = "1.0"
    intent: BassIntent


class BassPresetExchange(UnitModel):
    kind: Literal["human_bass_preset"] = "human_bass_preset"
    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=80)
    intent: BassIntent


class BassGenerationRecord(UnitModel):
    generation_id: int = Field(ge=1)
    pattern_id: str
    name: str
    created_at: str
    schema_version: str


class BassPreferenceRecord(UnitModel):
    candidate_a: str
    candidate_b: str
    selected: Literal["A", "B", "tie"]
    display_order: list[str]
    comparison_id: str | None = None
    decision_time_ms: int | None = None
    profile_scope: str | None = None
    created_at: str
    schema_version: str
