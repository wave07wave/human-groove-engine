from typing import Literal

import numpy as np

PhraseGrammar = Literal["AAAA", "AApAAx", "ABAB", "ABAC", "AApBA", "ABCA"]

GRAMMARS: tuple[PhraseGrammar, ...] = ("AAAA", "AApAAx", "ABAB", "ABAC", "AApBA", "ABCA")


def choose_grammar(rng: np.random.Generator, repetition: float, variation: float) -> PhraseGrammar:
    weights = np.array(
        [
            0.2 + repetition,
            0.4 + repetition + variation,
            0.3 + repetition,
            0.25 + variation,
            0.35 + variation,
            0.1 + variation,
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


def tension_curve(bars: int, development: float, hypnotic: float) -> list[float]:
    if bars == 1:
        return [0.35]
    curve = []
    for bar in range(bars):
        phase = bar / (bars - 1)
        rise_release = 1 - abs(phase * 2 - 1)
        curve.append(min(1.0, 0.2 + development * 0.55 * rise_release + hypnotic * 0.12))
    return curve
