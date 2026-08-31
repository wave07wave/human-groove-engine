from typing import Literal

import numpy as np

PhraseGrammar = Literal["AAAA", "AApAAx", "ABAB", "ABAC", "AApBA", "ABCA"]

GRAMMARS: tuple[PhraseGrammar, ...] = ("AAAA", "AApAAx", "ABAB", "ABAC", "AApBA", "ABCA")


def choose_grammar(rng: np.random.Generator, repetition: float, variation: float) -> PhraseGrammar:
    weights = np.array(
        [
            0.1 + 1.4 * repetition * (1 - variation * 0.55),
            0.15 + 0.8 * repetition + 0.35 * variation,
            0.12 + 0.9 * repetition,
            0.1 + 0.85 * variation + 0.25 * (1 - repetition),
            0.12 + 0.55 * variation + 0.25 * repetition,
            0.08 + 1.1 * variation + 0.5 * (1 - repetition),
        ]
    )
    weights /= weights.sum()
    return GRAMMARS[int(rng.choice(len(GRAMMARS), p=weights))]


def motif_for_bar(grammar: PhraseGrammar, bar: int) -> str:
    mapping = {
        "AAAA": ["A", "A", "A", "A"],
        "AApAAx": ["A", "A'", "A", "A''"],
        "ABAB": ["A", "B", "A", "B"],
        "ABAC": ["A", "B", "A", "C"],
        "AApBA": ["A", "A'", "B", "A"],
        "ABCA": ["A", "B", "C", "A"],
    }
    return mapping[grammar][bar % 4]


def tension_curve(
    bars: int,
    development: float,
    hypnotic: float,
    energy_curve: list[float] | None = None,
) -> list[float]:
    if energy_curve:
        if bars == 1:
            return [float(energy_curve[0])]
        source = np.linspace(0, 1, len(energy_curve))
        target = np.linspace(0, 1, bars)
        return [float(value) for value in np.interp(target, source, energy_curve)]
    if bars == 1:
        return [0.35]
    curve = []
    for bar in range(bars):
        phase = bar / (bars - 1)
        rise_release = 1 - abs(phase * 2 - 1)
        curve.append(min(1.0, 0.2 + development * 0.55 * rise_release + hypnotic * 0.12))
    return curve
