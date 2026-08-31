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
class HatPatternVariant:
    """A bounded one-bar vocabulary item, expressed in 8th/16th indices."""

    variant_id: str
    omit_eighths: tuple[int, ...] = ()
    add_sixteenths: tuple[int, ...] = ()
    accent_eighths: tuple[int, ...] = ()
    open_eighths: tuple[int, ...] = ()
    subdivision_scale: float = 1.0
    pickup_scale: float = 1.0
    open_scale: float = 1.0


@dataclass(frozen=True)
class DrumPatternVariant:
    """A coordinated kick/snare phrase cell, expressed in 16th indices."""

    variant_id: str
    kick_add_sixteenths: tuple[int, ...] = ()
    snare_ghost_sixteenths: tuple[int, ...] = ()
    snare_transition_sixteenths: tuple[int, ...] = ()
    kick_weak_scale: float = 1.0
    snare_ghost_scale: float = 1.0


@dataclass(frozen=True)
class PhraseArrangement:
    """A four-bar contour that steers the coordinated kit vocabularies."""

    arrangement_id: str
    vocabulary_offsets: tuple[int, ...]
    tension_scales: tuple[float, ...]


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


def _supports_binary_four_four_vocabulary(meter: MeterDefinition) -> bool:
    """Only apply 16th/offbeat templates when those positions are real grid slots."""
    return (meter.numerator, meter.denominator) == (4, 4) and (
        meter.subdivisions_per_quarter in (4, 8, 16)
    )


def _legal_grid_ticks(meter: MeterDefinition, ticks: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(tick for tick in ticks if tick % meter.subdivision_tick == 0)


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
            forced_kick_ticks=_legal_grid_ticks(meter, beats),
            reinforced_hat_ticks=_legal_grid_ticks(meter, offbeats),
            hat_probability=1.0 if _legal_grid_ticks(meter, offbeats) else 0.0,
        )
    if style == "Rock":
        return StyleRhythmProfile(
            forced_kick_ticks=_legal_grid_ticks(
                meter, tuple(tick for tick in (0, 2 * PPQ) if tick < meter.bar_ticks)
            ),
            reinforced_hat_ticks=_legal_grid_ticks(meter, eighths),
            hat_probability=1.0 if _legal_grid_ticks(meter, eighths) else 0.0,
        )
    if style == "Hip Hop":
        kick_ticks = tuple(tick for tick in (0, PPQ + PPQ // 2, 3 * PPQ) if tick < meter.bar_ticks)
        return StyleRhythmProfile(
            forced_kick_ticks=_legal_grid_ticks(meter, kick_ticks),
            reinforced_hat_ticks=_legal_grid_ticks(meter, eighths),
            hat_probability=0.58 if _legal_grid_ticks(meter, eighths) else 0.0,
        )
    return StyleRhythmProfile()


def style_hat_profile(style: str, meter: MeterDefinition) -> HatStyleProfile:
    """Return the style's rhythmic hat role when the pack supports the meter."""
    if not _supports_binary_four_four_vocabulary(meter):
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


def style_hat_variants(style: str, meter: MeterDefinition) -> tuple[HatPatternVariant, ...]:
    """Return several coherent vocabulary choices instead of one fixed loop."""
    if not _supports_binary_four_four_vocabulary(meter):
        return (HatPatternVariant("neutral-carrier"),)
    if style == "Funk":
        return (
            HatPatternVariant("funk-tight-16", accent_eighths=(0, 3, 6), open_eighths=(7,)),
            HatPatternVariant(
                "funk-linear-answer",
                omit_eighths=(2, 5),
                add_sixteenths=(3, 7, 11, 15),
                accent_eighths=(1, 4, 7),
                open_eighths=(3,),
                pickup_scale=1.25,
            ),
            HatPatternVariant(
                "funk-bark-turnaround",
                omit_eighths=(1, 6),
                add_sixteenths=(6, 14),
                accent_eighths=(0, 5),
                open_eighths=(5, 7),
                subdivision_scale=1.25,
                open_scale=1.35,
            ),
            HatPatternVariant(
                "funk-space-and-push",
                omit_eighths=(3, 4),
                add_sixteenths=(2, 10, 13),
                accent_eighths=(2, 6),
                pickup_scale=1.4,
            ),
        )
    if style == "Hip Hop":
        return (
            HatPatternVariant("hip-hop-head-nod", omit_eighths=(2, 6), accent_eighths=(0, 3, 5)),
            HatPatternVariant(
                "hip-hop-late-skitter",
                omit_eighths=(1, 5),
                add_sixteenths=(3, 7, 15),
                accent_eighths=(0, 4, 6),
                subdivision_scale=1.35,
            ),
            HatPatternVariant(
                "hip-hop-broken-loop",
                omit_eighths=(3, 4),
                add_sixteenths=(5, 11),
                accent_eighths=(1, 5, 7),
                pickup_scale=1.2,
            ),
            HatPatternVariant(
                "hip-hop-turnaround",
                omit_eighths=(1,),
                add_sixteenths=(13, 14, 15),
                accent_eighths=(0, 4),
                open_eighths=(7,),
                open_scale=1.25,
            ),
        )
    if style == "House":
        return (
            HatPatternVariant("house-classic-open", open_eighths=(1, 3, 5, 7)),
            HatPatternVariant(
                "house-closed-pump",
                open_eighths=(3, 7),
                accent_eighths=(1, 5),
                subdivision_scale=1.2,
            ),
            HatPatternVariant(
                "house-two-bar-lift",
                add_sixteenths=(6, 14),
                open_eighths=(5, 7),
                accent_eighths=(3, 7),
                open_scale=1.35,
            ),
            HatPatternVariant(
                "house-break-breathe",
                omit_eighths=(3,),
                add_sixteenths=(5, 6, 13, 14),
                open_eighths=(1, 7),
                subdivision_scale=1.35,
            ),
        )
    if style == "Rock":
        return (
            HatPatternVariant("rock-eighth-drive", accent_eighths=(0, 2, 4, 6)),
            HatPatternVariant(
                "rock-push-16",
                add_sixteenths=(3, 7, 11, 15),
                accent_eighths=(0, 4),
                pickup_scale=1.25,
            ),
            HatPatternVariant(
                "rock-open-chorus",
                open_eighths=(3, 7),
                accent_eighths=(1, 5),
                open_scale=1.3,
            ),
            HatPatternVariant(
                "rock-break-turnaround",
                omit_eighths=(5,),
                add_sixteenths=(10, 11, 14, 15),
                open_eighths=(7,),
                subdivision_scale=1.3,
            ),
        )
    # These choices are deliberately style-neutral so that Balanced and the
    # expressive intent presets also get fresh rhythmic shapes on every
    # generation, instead of silently falling back to one carrier loop.
    return (
        HatPatternVariant("adaptive-steady", accent_eighths=(0, 2, 4, 6)),
        HatPatternVariant(
            "adaptive-push",
            add_sixteenths=(3, 7, 11, 15),
            accent_eighths=(1, 5),
            pickup_scale=1.3,
        ),
        HatPatternVariant(
            "adaptive-space",
            omit_eighths=(3, 6),
            add_sixteenths=(5, 13),
            accent_eighths=(2, 7),
            open_eighths=(7,),
            subdivision_scale=1.2,
        ),
        HatPatternVariant(
            "adaptive-lift",
            omit_eighths=(4,),
            add_sixteenths=(6, 10, 14, 15),
            open_eighths=(3, 7),
            accent_eighths=(3, 7),
            subdivision_scale=1.35,
            open_scale=1.25,
        ),
    )


def style_drum_variants(style: str, meter: MeterDefinition) -> tuple[DrumPatternVariant, ...]:
    """Return kick/snare cells paired by index with the hat vocabularies."""
    if not _supports_binary_four_four_vocabulary(meter):
        return (DrumPatternVariant("neutral-drum-carrier"),)
    if style == "Funk":
        return (
            DrumPatternVariant("funk-pocket-lock", snare_ghost_sixteenths=(3, 11)),
            DrumPatternVariant(
                "funk-answer-kick",
                kick_add_sixteenths=(3, 10),
                snare_ghost_sixteenths=(6, 14),
                kick_weak_scale=1.18,
            ),
            DrumPatternVariant(
                "funk-early-push",
                kick_add_sixteenths=(6, 13),
                snare_transition_sixteenths=(15,),
                kick_weak_scale=1.28,
                snare_ghost_scale=1.2,
            ),
            DrumPatternVariant(
                "funk-turnaround",
                kick_add_sixteenths=(10, 14),
                snare_ghost_sixteenths=(5, 13),
                snare_transition_sixteenths=(15,),
                kick_weak_scale=1.34,
            ),
        )
    if style == "Hip Hop":
        return (
            DrumPatternVariant("hip-hop-head-nod", kick_add_sixteenths=(6,)),
            DrumPatternVariant(
                "hip-hop-late-answer",
                kick_add_sixteenths=(7, 13),
                snare_ghost_sixteenths=(14,),
                kick_weak_scale=1.15,
            ),
            DrumPatternVariant(
                "hip-hop-broken-pocket",
                kick_add_sixteenths=(5, 11),
                snare_ghost_sixteenths=(7,),
                snare_ghost_scale=1.22,
            ),
            DrumPatternVariant(
                "hip-hop-barline-turn",
                kick_add_sixteenths=(13, 15),
                snare_transition_sixteenths=(14,),
                kick_weak_scale=1.28,
            ),
        )
    if style == "House":
        return (
            DrumPatternVariant("house-four-floor", snare_ghost_sixteenths=(7, 15)),
            DrumPatternVariant(
                "house-pump-answer",
                kick_add_sixteenths=(6, 14),
                snare_ghost_sixteenths=(7,),
                kick_weak_scale=1.14,
            ),
            DrumPatternVariant(
                "house-two-bar-lift",
                kick_add_sixteenths=(7, 15),
                snare_transition_sixteenths=(14,),
                kick_weak_scale=1.2,
            ),
            DrumPatternVariant(
                "house-break-release",
                kick_add_sixteenths=(5, 13),
                snare_ghost_sixteenths=(6, 14),
                snare_transition_sixteenths=(15,),
                kick_weak_scale=1.25,
            ),
        )
    if style == "Rock":
        return (
            DrumPatternVariant("rock-straight-drive", snare_ghost_sixteenths=(7, 15)),
            DrumPatternVariant(
                "rock-push-16",
                kick_add_sixteenths=(3, 10),
                snare_ghost_sixteenths=(7,),
                kick_weak_scale=1.16,
            ),
            DrumPatternVariant(
                "rock-chorus-lift",
                kick_add_sixteenths=(6, 14),
                snare_transition_sixteenths=(15,),
                kick_weak_scale=1.22,
            ),
            DrumPatternVariant(
                "rock-turnaround",
                kick_add_sixteenths=(10, 11, 14),
                snare_ghost_sixteenths=(13,),
                snare_transition_sixteenths=(15,),
                kick_weak_scale=1.3,
            ),
        )
    return (
        DrumPatternVariant("adaptive-pocket", snare_ghost_sixteenths=(7, 15)),
        DrumPatternVariant(
            "adaptive-push",
            kick_add_sixteenths=(3, 10),
            snare_ghost_sixteenths=(6, 14),
            kick_weak_scale=1.15,
        ),
        DrumPatternVariant(
            "adaptive-space-answer",
            kick_add_sixteenths=(6, 13),
            snare_ghost_sixteenths=(5, 11),
            snare_ghost_scale=1.18,
        ),
        DrumPatternVariant(
            "adaptive-lift",
            kick_add_sixteenths=(10, 14, 15),
            snare_transition_sixteenths=(13,),
            kick_weak_scale=1.28,
        ),
    )


def style_phrase_arrangements(style: str, meter: MeterDefinition) -> tuple[PhraseArrangement, ...]:
    """Offer several 4-bar narratives, without changing the meter's anchors."""
    if not _supports_binary_four_four_vocabulary(meter):
        return (PhraseArrangement("neutral-phrase", (0,), (1.0,)),)
    if style == "Funk":
        return (
            PhraseArrangement("funk-pocket-arc", (0, 0, 1, 3), (0.84, 0.94, 1.02, 1.18)),
            PhraseArrangement("funk-question-answer", (1, 2, 1, 3), (0.88, 1.02, 0.94, 1.2)),
            PhraseArrangement("funk-early-spark", (2, 0, 1, 3), (1.02, 0.86, 0.98, 1.16)),
            PhraseArrangement("funk-space-return", (3, 0, 2, 1), (0.8, 1.0, 1.12, 0.92)),
        )
    if style == "Hip Hop":
        return (
            PhraseArrangement("hip-hop-head-nod", (0, 0, 1, 3), (0.92, 0.94, 1.02, 1.12)),
            PhraseArrangement("hip-hop-late-reply", (1, 0, 2, 3), (0.86, 0.98, 0.94, 1.18)),
            PhraseArrangement("hip-hop-broken-return", (2, 1, 0, 3), (1.0, 0.9, 0.96, 1.14)),
            PhraseArrangement("hip-hop-turnaround", (0, 2, 1, 3), (0.9, 1.02, 0.96, 1.22)),
        )
    if style == "House":
        return (
            PhraseArrangement("house-lane-lift", (0, 0, 2, 3), (0.92, 0.96, 1.06, 1.2)),
            PhraseArrangement("house-pump-release", (1, 0, 1, 3), (1.0, 0.9, 1.02, 1.16)),
            PhraseArrangement("house-two-bar-answer", (0, 2, 0, 3), (0.94, 1.04, 0.96, 1.22)),
            PhraseArrangement("house-break-reentry", (3, 0, 1, 2), (0.82, 1.04, 1.1, 0.94)),
        )
    if style == "Rock":
        return (
            PhraseArrangement("rock-drive-lift", (0, 0, 2, 3), (0.94, 0.98, 1.08, 1.2)),
            PhraseArrangement("rock-push-answer", (1, 2, 0, 3), (1.02, 0.94, 1.0, 1.18)),
            PhraseArrangement("rock-chorus-rise", (2, 0, 1, 3), (0.98, 0.9, 1.12, 1.22)),
            PhraseArrangement("rock-break-return", (3, 0, 1, 2), (0.82, 1.04, 1.1, 0.96)),
        )
    return (
        PhraseArrangement("adaptive-steady-lift", (0, 0, 1, 3), (0.9, 0.96, 1.04, 1.18)),
        PhraseArrangement("adaptive-question-answer", (1, 2, 0, 3), (0.92, 1.04, 0.96, 1.2)),
        PhraseArrangement("adaptive-delayed-release", (0, 1, 2, 3), (0.86, 0.94, 1.08, 1.22)),
        PhraseArrangement("adaptive-contrast-return", (3, 0, 2, 1), (0.8, 1.06, 1.12, 0.92)),
    )
