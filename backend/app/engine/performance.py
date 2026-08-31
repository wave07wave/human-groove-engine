from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import PERFORMANCE_MODEL_PATH
from app.models.event import InstrumentID
from app.random.seeds import HierarchicalRNG

POSITION_BUCKETS = ("downbeat", "beat", "off_eighth", "weak_sixteenth")
TEMPO_BUCKETS = ("slow", "medium", "fast")
PHRASE_BUCKETS = ("opening", "middle", "closing")


class InstrumentPerformance(BaseModel):
    count: int = Field(ge=0)
    timing_mean_us: float = Field(ge=-25_000, le=25_000)
    timing_residual_std_us: float = Field(ge=0, le=25_000)
    velocity_mean: float = Field(ge=1, le=127)
    velocity_residual_std: float = Field(ge=0, le=50)
    timing_loading: float = Field(ge=-2, le=2)
    velocity_loading: float = Field(ge=-2, le=2)


class StylePerformance(BaseModel):
    source_genres: list[str]
    hit_count: int = Field(ge=1)
    shared_timing_std_us: float = Field(ge=0, le=25_000)
    shared_velocity_std: float = Field(ge=0, le=50)
    instruments: dict[str, InstrumentPerformance]
    position_timing_us: dict[str, float]
    position_velocity: dict[str, float]
    tempo_timing_us: dict[str, float]
    tempo_velocity: dict[str, float]
    phrase_timing_us: dict[str, float]
    phrase_velocity: dict[str, float]

    @model_validator(mode="after")
    def complete_conditioning_tables(self) -> "StylePerformance":
        required_instruments = {instrument.value for instrument in InstrumentID}
        if not required_instruments.issubset(self.instruments):
            raise ValueError("performance model is missing supported instruments")
        for values, required, label in (
            (self.position_timing_us, POSITION_BUCKETS, "position timing"),
            (self.position_velocity, POSITION_BUCKETS, "position velocity"),
            (self.tempo_timing_us, TEMPO_BUCKETS, "tempo timing"),
            (self.tempo_velocity, TEMPO_BUCKETS, "tempo velocity"),
            (self.phrase_timing_us, PHRASE_BUCKETS, "phrase timing"),
            (self.phrase_velocity, PHRASE_BUCKETS, "phrase velocity"),
        ):
            if not set(required).issubset(values):
                raise ValueError(f"performance model is missing {label} buckets")
            if not all(math.isfinite(value) for value in values.values()):
                raise ValueError(f"performance model has non-finite {label} values")
        return self


class PerformanceModel(BaseModel):
    schema_version: str
    model_id: str
    model_version: str
    dataset: dict[str, str | int | float]
    styles: dict[str, StylePerformance]
    validation: dict[str, int | float | str]

    @model_validator(mode="after")
    def balanced_fallback_exists(self) -> "PerformanceModel":
        if self.schema_version != "1.0":
            raise ValueError("unsupported performance model schema")
        if "Balanced" not in self.styles:
            raise ValueError("performance model requires a Balanced style")
        return self


@dataclass(frozen=True)
class PerformanceAdjustment:
    timing_us: float
    target_velocity: float


def tempo_bucket(bpm: float) -> str:
    if bpm < 90:
        return "slow"
    if bpm < 125:
        return "medium"
    return "fast"


def position_bucket(slot: int, subdivisions_per_quarter: int) -> str:
    within_beat = slot % subdivisions_per_quarter
    if slot == 0:
        return "downbeat"
    if within_beat == 0:
        return "beat"
    phase = within_beat / subdivisions_per_quarter
    if abs(phase - 0.5) <= 0.17:
        return "off_eighth"
    return "weak_sixteenth"


def phrase_bucket(bar: int, bars: int) -> str:
    if bar == 0:
        return "opening"
    if bar == bars - 1 or bar % 4 == 3:
        return "closing"
    return "middle"


@lru_cache(maxsize=8)
def load_performance_model(path: str | Path = PERFORMANCE_MODEL_PATH) -> PerformanceModel | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return PerformanceModel.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError, TypeError):
        return None


def model_status(path: str | Path = PERFORMANCE_MODEL_PATH) -> dict[str, str | bool | int]:
    model = load_performance_model(path)
    if model is None:
        return {"available": False, "active": "rule-pocket-v1"}
    return {
        "available": True,
        "active": model.model_id,
        "version": model.model_version,
        "training_hits": int(model.dataset.get("training_hits", 0)),
    }


def performance_adjustment(
    model: PerformanceModel,
    *,
    hrng: HierarchicalRNG,
    style: str,
    bpm: float,
    instrument: InstrumentID,
    bar: int,
    bars: int,
    slot: int,
    subdivisions_per_quarter: int,
    candidate: int,
) -> PerformanceAdjustment:
    profile = model.styles.get(style, model.styles["Balanced"])
    instrument_profile = profile.instruments[instrument.value]
    position = position_bucket(slot, subdivisions_per_quarter)
    tempo = tempo_bucket(bpm)
    phrase = phrase_bucket(bar, bars)
    shared = hrng.stream("performance-shared", model.model_id, candidate, bar, slot)
    residual = hrng.stream(
        "performance-residual", model.model_id, candidate, instrument.value, bar, slot
    )
    shared_timing = float(shared.normal()) * profile.shared_timing_std_us
    shared_velocity = float(shared.normal()) * profile.shared_velocity_std
    timing = (
        instrument_profile.timing_mean_us
        + profile.position_timing_us[position]
        + profile.tempo_timing_us[tempo]
        + profile.phrase_timing_us[phrase]
        + instrument_profile.timing_loading * shared_timing
        + float(residual.normal()) * instrument_profile.timing_residual_std_us
    )
    velocity = (
        instrument_profile.velocity_mean
        + profile.position_velocity[position]
        + profile.tempo_velocity[tempo]
        + profile.phrase_velocity[phrase]
        + instrument_profile.velocity_loading * shared_velocity
        + float(residual.normal()) * instrument_profile.velocity_residual_std
    )
    return PerformanceAdjustment(timing_us=timing, target_velocity=velocity)
