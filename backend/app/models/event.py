from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class InstrumentID(StrEnum):
    KICK = "kick"
    SNARE = "snare"
    CLOSED_HAT = "closed_hat"
    OPEN_HAT = "open_hat"
    PERCUSSION = "percussion"
    BASS = "bass"


class EventRole(StrEnum):
    ANCHOR = "anchor"
    CONFIRMATION = "confirmation"
    ANTICIPATION = "anticipation"
    VIOLATION = "violation"
    OMISSION_PROXY = "omission_proxy"
    RECOVERY = "recovery"
    GHOST = "ghost"
    DECORATION = "decoration"
    TRANSITION = "transition"


class DurationStyle(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    LEGATO = "legato"
    STACCATO = "staccato"
    OVERLAP = "overlap"
    CHOKE = "choke"


class GrooveEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument: InstrumentID
    grid_tick: int = Field(ge=0)
    structural_offset_tick: int = 0
    micro_offset_us: int = Field(default=0, ge=-25_000, le=25_000)
    duration_tick: int = Field(gt=0)
    velocity: int = Field(ge=1, le=127)
    pitch: int | None = Field(default=None, ge=0, le=127)
    primary_role: EventRole = EventRole.DECORATION
    role_tags: set[EventRole] = Field(default_factory=set)
    accent: float = Field(default=0.5, ge=0, le=1)
    timbre_variant: str | None = None
    duration_style: DurationStyle = DurationStyle.MEDIUM
    choke_group: str | None = None
    locked: bool = False
    origin: Literal["generated", "user_edited", "regenerated"] = "generated"

    @model_validator(mode="after")
    def performed_time_nonnegative(self) -> "GrooveEvent":
        if self.grid_tick + self.structural_offset_tick < 0:
            raise ValueError("performed tick cannot be negative")
        return self

    @property
    def performed_tick(self) -> int:
        return max(0, self.grid_tick + self.structural_offset_tick)
