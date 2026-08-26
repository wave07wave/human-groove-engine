"""Measure deterministic HGE × HBE CO-CREATE generation on the local runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bass.interaction import (
    IntegrationMode,
    JointGenerateRequest,
    generate_joint_candidates,
)
from app.bass.models import BassGenerateRequest
from app.engine.generator import generate_pattern
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition


def benchmark(bars: int, candidates: int, iterations: int) -> dict[str, float | int]:
    meter = MeterDefinition.from_name("4/4")
    groove = generate_pattern(
        bpm=112,
        bars=bars,
        meter=meter,
        intent=GrooveIntent(),
        seed=20260826,
    )
    request = JointGenerateRequest(
        groove_pattern=groove,
        bass_request=BassGenerateRequest(
            bpm=112,
            bars=bars,
            meter=meter,
            harmony="Dm7 | G7 | Cmaj7 | A7",
            seed=20260826,
            candidate_count=candidates,
        ),
        mode=IntegrationMode.CO_CREATE,
        candidate_count=candidates,
    )
    samples: list[float] = []
    for _ in range(iterations):
        started = perf_counter()
        response = generate_joint_candidates(request)
        samples.append(perf_counter() - started)
        if len(response.candidates) != candidates:
            raise RuntimeError("candidate count changed during benchmark")
    return {
        "bars": bars,
        "candidates": candidates,
        "iterations": iterations,
        "median_seconds": round(median(samples), 6),
        "min_seconds": round(min(samples), 6),
        "max_seconds": round(max(samples), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=int, default=8, choices=(1, 2, 4, 8, 16, 32, 64))
    parser.add_argument("--candidates", type=int, default=4, choices=(1, 2, 3, 4))
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    print(json.dumps(benchmark(args.bars, args.candidates, args.iterations), indent=2))


if __name__ == "__main__":
    main()
