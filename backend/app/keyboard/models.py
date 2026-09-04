from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.bass.models import HarmonyTimeline, KeyContext, ScaleMode, TempoMap
from app.config import (
    ANALYSIS_VERSION,
    ENGINE_VERSION,
    RNG_ALGORITHM,
    SCHEMA_VERSION,
)
from app.models.meter import MeterDefinition


class UnitModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


KeyboardStyleMode = Literal["standard", "earl", "joe", "johnny", "blend"]
KeyboardInstrument = Literal[
    "acoustic_piano", "tonewheel_organ", "electric_piano", "celeste"
]
KeyboardRole = Literal["anchor", "comp", "answer", "fill", "grace", "resolution"]
KeyboardHand = Literal["left", "right", "both"]
KeyboardArticulation = Literal["staccato", "normal", "tenuto", "legato"]


class KeyboardBlend(UnitModel):
    earl: float = Field(1 / 3, ge=0, le=1)
    joe: float = Field(1 / 3, ge=0, le=1)
    johnny: float = Field(1 / 3, ge=0, le=1)

    @model_validator(mode="after")
    def at_least_one_influence(self) -> "KeyboardBlend":
        if self.earl + self.joe + self.johnny <= 0:
            raise ValueError("at least one keyboard blend influence must be greater than zero")
        return self


class DetroitKeyboardSettings(UnitModel):
    """Independent, attribution-safe keyboard performance-language layer."""

    mode: KeyboardStyleMode = "standard"
    blend: KeyboardBlend = Field(default_factory=KeyboardBlend)


class KeyboardRhythmContext(UnitModel):
    kick_ticks: list[int] = Field(default_factory=list)
    snare_ticks: list[int] = Field(default_factory=list)
    bass_ticks: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def non_negative_ticks(self) -> "KeyboardRhythmContext":
        if any(tick < 0 for tick in self.kick_ticks + self.snare_ticks + self.bass_ticks):
            raise ValueError("rhythm context ticks must be non-negative")
        return self


class KeyboardEvent(UnitModel):
    event_id: str
    grid_tick: int = Field(ge=0)
    micro_offset_us: int = Field(default=0, ge=-25_000, le=25_000)
    duration_tick: int = Field(gt=0)
    pitches: list[int] = Field(min_length=1, max_length=7)
    velocities: list[int] = Field(min_length=1, max_length=7)
    instrument: KeyboardInstrument = "acoustic_piano"
    role: KeyboardRole = "comp"
    hand: KeyboardHand = "right"
    articulation: KeyboardArticulation = "normal"
    locked: bool = False
    origin: Literal["generated", "regenerated", "user_edited"] = "generated"

    @model_validator(mode="after")
    def valid_chord(self) -> "KeyboardEvent":
        if len(self.pitches) != len(self.velocities):
            raise ValueError("each keyboard pitch must have one velocity")
        if len(set(self.pitches)) != len(self.pitches):
            raise ValueError("keyboard event pitches must be unique")
        if any(not 0 <= pitch <= 127 for pitch in self.pitches):
            raise ValueError("keyboard pitch must be a MIDI note")
        if any(not 1 <= velocity <= 127 for velocity in self.velocities):
            raise ValueError("keyboard velocity must be between 1 and 127")
        object.__setattr__(self, "pitches", sorted(self.pitches))
        return self

    @property
    def performed_tick(self) -> int:
        return self.grid_tick


class KeyboardAnalysis(UnitModel):
    onsets_per_bar: float = Field(ge=0)
    syncopation_ratio: float = Field(ge=0, le=1)
    mean_velocity: float = Field(ge=0, le=127)
    velocity_spread: float = Field(ge=0)
    timing_mean_us: float
    timing_spread_us: float = Field(ge=0)
    register_mean: float = Field(ge=0, le=127)
    voicing_span: float = Field(ge=0)
    notes_per_onset: float = Field(ge=0)
    left_hand_ratio: float = Field(ge=0, le=1)
    melodic_ratio: float = Field(ge=0, le=1)
    grace_ratio: float = Field(ge=0, le=1)
    phrase_variation: float = Field(ge=0)
    context_alignment: float = Field(ge=0, le=1)
    final_resolution: float = Field(ge=0, le=1)
    instrument_distribution: dict[str, float] = Field(default_factory=dict)


class KeyboardPatternMetadata(UnitModel):
    engine_version: str = ENGINE_VERSION
    schema_version: str = SCHEMA_VERSION
    analysis_version: str = ANALYSIS_VERSION
    rng_algorithm: str = RNG_ALGORITHM
    master_seed: int = Field(ge=0)
    candidate_index: int = Field(default=0, ge=0)
    revision: int = Field(default=0, ge=0)
    detroit_keyboard: DetroitKeyboardSettings = Field(
        default_factory=DetroitKeyboardSettings
    )
    generation_notes: list[str] = Field(default_factory=list)


class KeyboardPattern(UnitModel):
    pattern_id: str
    name: str = "Generated Keys"
    bpm: float = Field(100, ge=30, le=300)
    bars: int = Field(4, ge=1, le=64)
    meter: MeterDefinition
    tempo_map: TempoMap
    harmony_text: str = "Cmaj7"
    harmony: HarmonyTimeline
    key_context: KeyContext | None = None
    events: list[KeyboardEvent]
    rhythm_context: KeyboardRhythmContext = Field(default_factory=KeyboardRhythmContext)
    bar_locks: list[int] = Field(default_factory=list)
    metadata: KeyboardPatternMetadata
    analysis: KeyboardAnalysis | None = None

    @model_validator(mode="after")
    def structural_integrity(self) -> "KeyboardPattern":
        end_tick = self.bars * self.meter.bar_ticks
        ids = {event.event_id for event in self.events}
        if len(ids) != len(self.events):
            raise ValueError("keyboard event IDs must be unique")
        if any(event.grid_tick >= end_tick for event in self.events):
            raise ValueError("keyboard event outside pattern")
        if any(event.grid_tick + event.duration_tick > end_tick for event in self.events):
            raise ValueError("keyboard duration exceeds pattern")
        if any(bar < 0 or bar >= self.bars for bar in self.bar_locks):
            raise ValueError("keyboard bar lock outside pattern")
        object.__setattr__(
            self,
            "events",
            sorted(self.events, key=lambda event: (event.grid_tick, event.event_id)),
        )
        object.__setattr__(self, "bar_locks", sorted(set(self.bar_locks)))
        return self


class KeyboardGenerateRequest(UnitModel):
    bpm: float = Field(100, ge=30, le=300)
    bars: int = Field(4, ge=1, le=64)
    meter: MeterDefinition = Field(default_factory=lambda: MeterDefinition.from_name("4/4"))
    harmony: str = "Dm7 | G7 | Cmaj7 | A7"
    key: str | None = "C"
    mode: ScaleMode = ScaleMode.MAJOR
    seed: int = Field(42, ge=0)
    candidate_count: int = Field(4, ge=1, le=4)
    detroit_keyboard: DetroitKeyboardSettings = Field(
        default_factory=DetroitKeyboardSettings
    )
    rhythm_context: KeyboardRhythmContext = Field(default_factory=KeyboardRhythmContext)


class KeyboardGenerateResponse(UnitModel):
    candidates: list[KeyboardPattern]


class KeyboardMutateRequest(UnitModel):
    pattern: KeyboardPattern
    bars: set[int] = Field(default_factory=set)


class KeyboardGenerationRecord(UnitModel):
    generation_id: int = Field(ge=1)
    pattern_id: str
    name: str
    style: KeyboardStyleMode
    created_at: str
    schema_version: str


class KeyboardPatternExchange(UnitModel):
    kind: Literal["human_keyboard_pattern"] = "human_keyboard_pattern"
    schema_version: Literal["1.0"] = "1.0"
    pattern: KeyboardPattern
