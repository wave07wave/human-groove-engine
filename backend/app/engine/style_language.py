from __future__ import annotations

from dataclasses import dataclass

from app.config import PPQ
from app.models.meter import MeterDefinition


@dataclass(frozen=True)
class StyleRhythmProfile:
    forced_kick_ticks: tuple[int, ...] = ()
    reinforced_hat_ticks: tuple[int, ...] = ()
    hat_probability: float = 0.0


@dataclass(frozen=True)
class StyleKnowledgePack:
    pack_id: str
    version: str
    meter_scope: tuple[int, ...]
    source_scope: str
    caveat: str


_PACKS = {
    "Funk": StyleKnowledgePack(
        "funk-western-quarter-v1",
        "1.0",
        (4,),
        "Existing built-in Funk vocabulary",
        "A starter vocabulary, not a cultural or listener identity inference.",
    ),
    "Hip Hop": StyleKnowledgePack(
        "hip-hop-western-quarter-v1",
        "1.0",
        (4,),
        "Existing built-in Hip Hop vocabulary",
        "A starter vocabulary, not a cultural or listener identity inference.",
    ),
    "House": StyleKnowledgePack(
        "house-western-quarter-v1",
        "1.0",
        (4,),
        "Existing built-in House vocabulary",
        "A starter vocabulary, not a cultural or listener identity inference.",
    ),
    "Rock": StyleKnowledgePack(
        "rock-western-quarter-v1",
        "1.0",
        (4,),
        "Existing built-in Rock vocabulary",
        "A starter vocabulary, not a cultural or listener identity inference.",
    ),
}


def style_knowledge_pack(style: str, meter: MeterDefinition) -> StyleKnowledgePack:
    pack = _PACKS.get(style)
    if pack and meter.denominator in pack.meter_scope:
        return pack
    return StyleKnowledgePack(
        "neutral-v1",
        "1.0",
        (),
        "Meter-aware neutral generator",
        "No culture or style prior is applied outside a declared pack scope.",
    )


def style_rhythm_profile(style: str, meter: MeterDefinition) -> StyleRhythmProfile:
    """Return explicit genre landmarks while leaving unknown/user styles neutral."""
    if meter.denominator != 4:
        return StyleRhythmProfile()
    beats = tuple(range(0, meter.bar_ticks, PPQ))
    eighths = tuple(range(0, meter.bar_ticks, PPQ // 2))
    offbeats = tuple(tick + PPQ // 2 for tick in beats if tick + PPQ // 2 < meter.bar_ticks)
    if style == "House":
        return StyleRhythmProfile(
            forced_kick_ticks=beats,
            reinforced_hat_ticks=offbeats,
            hat_probability=1.0,
        )
    if style == "Rock":
        return StyleRhythmProfile(
            forced_kick_ticks=tuple(tick for tick in (0, 2 * PPQ) if tick < meter.bar_ticks),
            reinforced_hat_ticks=eighths,
            hat_probability=1.0,
        )
    if style == "Hip Hop":
        kick_ticks = tuple(tick for tick in (0, PPQ + PPQ // 2, 3 * PPQ) if tick < meter.bar_ticks)
        return StyleRhythmProfile(
            forced_kick_ticks=kick_ticks,
            reinforced_hat_ticks=eighths,
            hat_probability=0.58,
        )
    return StyleRhythmProfile()
