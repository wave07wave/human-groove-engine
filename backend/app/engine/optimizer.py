from __future__ import annotations

from app.analysis.listener import analyze_pattern
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.models.pattern import GroovePattern

from .generator import generate_pattern


def pattern_distance(a: GroovePattern, b: GroovePattern) -> float:
    left = {(e.instrument.value, e.grid_tick, e.primary_role.value) for e in a.events}
    right = {(e.instrument.value, e.grid_tick, e.primary_role.value) for e in b.events}
    event_distance = 1 - len(left & right) / max(1, len(left | right))
    adna = a.analysis.measured_dna.model_dump() if a.analysis else {}
    bdna = b.analysis.measured_dna.model_dump() if b.analysis else {}
    dna_distance = sum(abs(adna[k] - bdna[k]) for k in adna) / max(1, len(adna))
    return 0.75 * event_distance + 0.25 * dna_distance


def generate_candidates(
    *,
    bpm: float,
    bars: int,
    meter: MeterDefinition,
    intent: GrooveIntent,
    seed: int,
    count: int = 4,
    mode: str = "preview",
    preset: str = "Balanced",
) -> list[GroovePattern]:
    pool_size = 10 if mode == "preview" else 24
    pool: list[GroovePattern] = []
    for candidate in range(pool_size):
        pattern = generate_pattern(
            bpm=bpm,
            bars=bars,
            meter=meter,
            intent=intent,
            seed=seed,
            candidate=candidate,
            name=f"{preset} · {chr(65 + candidate)}",
        )
        pattern.analysis = analyze_pattern(pattern)
        pool.append(pattern)
    pool.sort(key=lambda item: item.analysis.fitness if item.analysis else 0, reverse=True)
    selected = [pool.pop(0)]
    while pool and len(selected) < count:
        candidate = max(
            pool,
            key=lambda item: 0.8 * (item.analysis.fitness if item.analysis else 0)
            + 0.2 * min(pattern_distance(item, chosen) for chosen in selected),
        )
        selected.append(candidate)
        pool.remove(candidate)
    for index, item in enumerate(selected):
        item.name = f"{preset} · {chr(65 + index)}"
    return selected
