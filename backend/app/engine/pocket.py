from __future__ import annotations

from dataclasses import dataclass

from app.config import INSTRUMENT_OFFSETS_US


@dataclass(frozen=True)
class PocketProfile:
    offsets_us: dict[str, int]
    jitter_us: int = 900
    phrase_contour_us: int = 3_500


def _profile(
    *,
    kick: int,
    snare: int,
    closed_hat: int,
    open_hat: int,
    percussion: int,
    bass: int,
    jitter: int = 900,
    contour: int = 3_500,
) -> PocketProfile:
    return PocketProfile(
        offsets_us={
            "kick": kick,
            "snare": snare,
            "closed_hat": closed_hat,
            "open_hat": open_hat,
            "percussion": percussion,
            "bass": bass,
        },
        jitter_us=jitter,
        phrase_contour_us=contour,
    )


POCKETS: dict[str, PocketProfile] = {
    "Balanced": _profile(
        kick=0, snare=7_000, closed_hat=-3_000, open_hat=-2_000, percussion=2_000, bass=5_000
    ),
    "Funk": _profile(
        kick=-700,
        snare=5_500,
        closed_hat=-2_600,
        open_hat=-1_800,
        percussion=1_000,
        bass=2_200,
        jitter=650,
        contour=2_200,
    ),
    "Hip Hop": _profile(
        kick=1_200,
        snare=8_500,
        closed_hat=800,
        open_hat=1_200,
        percussion=3_800,
        bass=6_800,
        jitter=750,
        contour=3_800,
    ),
    "House": _profile(
        kick=-300,
        snare=1_800,
        closed_hat=-1_400,
        open_hat=-1_000,
        percussion=500,
        bass=1_500,
        jitter=420,
        contour=900,
    ),
    "Rock": _profile(
        kick=-700,
        snare=2_800,
        closed_hat=-900,
        open_hat=-700,
        percussion=900,
        bass=1_200,
        jitter=600,
        contour=1_800,
    ),
    "Laid Back": _profile(
        kick=1_500,
        snare=10_500,
        closed_hat=500,
        open_hat=1_000,
        percussion=4_500,
        bass=7_500,
        jitter=850,
        contour=4_000,
    ),
    "Forward": _profile(
        kick=-2_500,
        snare=-900,
        closed_hat=-4_500,
        open_hat=-3_500,
        percussion=-1_500,
        bass=-1_000,
        jitter=700,
        contour=2_400,
    ),
    "Hypnotic": _profile(
        kick=0,
        snare=3_500,
        closed_hat=-1_000,
        open_hat=-800,
        percussion=500,
        bass=2_000,
        jitter=400,
        contour=900,
    ),
    "Broken": _profile(
        kick=-1_500,
        snare=8_500,
        closed_hat=-3_800,
        open_hat=1_500,
        percussion=4_000,
        bass=5_500,
        jitter=1_150,
        contour=4_500,
    ),
    "Minimal": _profile(
        kick=0,
        snare=4_500,
        closed_hat=-1_500,
        open_hat=-1_000,
        percussion=1_000,
        bass=2_500,
        jitter=450,
        contour=1_200,
    ),
    "Swing": _profile(
        kick=500,
        snare=7_500,
        closed_hat=-1_500,
        open_hat=-800,
        percussion=2_800,
        bass=5_800,
        jitter=900,
        contour=3_800,
    ),
    "Mechanical": _profile(
        kick=0, snare=0, closed_hat=0, open_hat=0, percussion=0, bass=0, jitter=120, contour=0
    ),
    "Loose": _profile(
        kick=-1_000,
        snare=9_000,
        closed_hat=-4_000,
        open_hat=1_500,
        percussion=5_000,
        bass=7_000,
        jitter=1_400,
        contour=5_200,
    ),
}


def pocket_for(style: str) -> PocketProfile:
    if style in POCKETS:
        return POCKETS[style]
    return PocketProfile(offsets_us=dict(INSTRUMENT_OFFSETS_US))
