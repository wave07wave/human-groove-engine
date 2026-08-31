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
class HatStyleProfile:
    """Declared, bounded hi-hat vocabulary for a built-in style.

    These are musical starting points, not claims about every performer or
    cultural variant of a genre.  Unknown styles use the neutral profile.
    """

    profile_id: str = "neutral-hat-v1"
    spine: str = "eighth"
    spine_probability: float = 0.72
    subdivision_bias: float = 0.0
    pickup_bias: float = 0.0
    open_bias: float = 0.0
    linear_bias: float = 0.0
    backbeat_space: float = 0.0
    open_replaces_closed: bool = False
    two_bar_variation: bool = False


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


def style_hat_profile(style: str, meter: MeterDefinition) -> HatStyleProfile:
    """Return the style's rhythmic hat role when the pack supports the meter."""
    if (meter.numerator, meter.denominator) != (4, 4):
        return HatStyleProfile()
    if style == "Funk":
        return HatStyleProfile(
            profile_id="funk-16th-linear-v1",
            spine="sixteenth",
            spine_probability=0.64,
            subdivision_bias=0.48,
            pickup_bias=0.52,
            open_bias=0.52,
            linear_bias=0.48,
            backbeat_space=0.5,
        )
    if style == "Hip Hop":
        return HatStyleProfile(
            profile_id="hip-hop-pocket-8th-v1",
            spine="eighth",
            spine_probability=0.68,
            subdivision_bias=0.16,
            pickup_bias=0.24,
            open_bias=0.18,
            linear_bias=0.08,
            backbeat_space=0.28,
        )
    if style == "House":
        return HatStyleProfile(
            profile_id="house-offbeat-909-v1",
            spine="offbeat",
            spine_probability=1.0,
            subdivision_bias=0.16,
            pickup_bias=0.08,
            open_bias=0.74,
            linear_bias=0.08,
            backbeat_space=0.04,
            open_replaces_closed=True,
            two_bar_variation=True,
        )
    if style == "Rock":
        return HatStyleProfile(
            profile_id="rock-eighth-drive-v1",
            spine="eighth",
            spine_probability=0.94,
            subdivision_bias=0.24,
            pickup_bias=0.2,
            open_bias=0.42,
            linear_bias=0.12,
            backbeat_space=0.14,
        )
    return HatStyleProfile()
