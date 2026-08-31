#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import mido
import numpy as np

from app.engine.performance import (
    PHRASE_BUCKETS,
    POSITION_BUCKETS,
    TEMPO_BUCKETS,
    PerformanceModel,
    phrase_bucket,
    position_bucket,
    tempo_bucket,
)

DATASET_SHA256 = "651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"
DATASET_URL = (
    "https://storage.googleapis.com/magentadata/datasets/groove/"
    "groove-v1.0.0-midionly.zip"
)

STYLE_GENRES = {
    "Balanced": {
        "afrobeat", "afrocuban", "blues", "country", "dance", "funk", "gospel",
        "highlife", "hiphop", "jazz", "latin", "middleeastern", "neworleans", "pop",
        "punk", "reggae", "rock", "soul",
    },
    "Funk": {"funk", "soul", "gospel", "neworleans", "hiphop"},
    "Laid Back": {"hiphop", "soul", "reggae", "blues"},
    "Forward": {"rock", "punk", "dance", "afrobeat"},
    "Hypnotic": {"dance", "highlife", "afrobeat", "reggae"},
    "Broken": {"jazz", "afrocuban", "latin", "neworleans", "middleeastern"},
    "Minimal": {"pop", "country", "reggae", "blues"},
    "Swing": {"jazz", "blues", "neworleans"},
    "Mechanical": {"dance", "pop", "rock", "punk"},
    "Loose": {"jazz", "blues", "neworleans", "soul"},
}

GENRE_STYLE = {
    "funk": "Funk", "gospel": "Funk", "soul": "Funk",
    "hiphop": "Laid Back", "reggae": "Laid Back",
    "rock": "Forward", "punk": "Forward",
    "dance": "Hypnotic", "highlife": "Hypnotic", "afrobeat": "Hypnotic",
    "jazz": "Swing", "neworleans": "Swing", "blues": "Swing",
    "afrocuban": "Broken", "latin": "Broken", "middleeastern": "Broken",
    "pop": "Minimal", "country": "Minimal",
}

PITCH_INSTRUMENT = {
    36: "kick",
    37: "snare", 38: "snare", 40: "snare",
    22: "closed_hat", 42: "closed_hat", 44: "closed_hat",
    26: "open_hat", 46: "open_hat",
}
BASE_VELOCITY = {
    "kick": 94, "snare": 96, "closed_hat": 72, "open_hat": 78, "percussion": 70,
}


@dataclass(frozen=True)
class Hit:
    filename: str
    quantized_tick: int
    instrument: str
    genre: str
    bpm: float
    position: str
    phrase: str
    tempo: str
    timing_us: float
    velocity: float


def _instrument(note: int) -> str:
    return PITCH_INSTRUMENT.get(note, "percussion")


def _read_hits(dataset_root: Path, split: str) -> tuple[list[Hit], int]:
    hits: list[Hit] = []
    files = 0
    with (dataset_root / "info.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["split"] != split or row["beat_type"] != "beat":
            continue
        if row["time_signature"] != "4-4":
            continue
        path = dataset_root / row["midi_filename"]
        midi = mido.MidiFile(path)
        files += 1
        absolute_tick = 0
        step_tick = midi.ticks_per_beat / 4
        bar_tick = midi.ticks_per_beat * 4
        bpm = float(row["bpm"])
        genre = row["style"].split("/", 1)[0]
        for message in mido.merge_tracks(midi.tracks):
            absolute_tick += message.time
            if message.type != "note_on" or message.velocity <= 0:
                continue
            quantized_tick = round(absolute_tick / step_tick) * step_tick
            offset_tick = absolute_tick - quantized_tick
            timing_us = offset_tick / midi.ticks_per_beat * 60_000_000 / bpm
            if abs(timing_us) > 62_500:
                continue
            slot = int(round(quantized_tick / step_tick))
            bar = int(quantized_tick // bar_tick)
            hits.append(
                Hit(
                    filename=row["midi_filename"],
                    quantized_tick=int(round(quantized_tick)),
                    instrument=_instrument(message.note),
                    genre=genre,
                    bpm=bpm,
                    position=position_bucket(slot % 16, 4),
                    phrase=phrase_bucket(bar % 4, 4),
                    tempo=tempo_bucket(bpm),
                    timing_us=float(timing_us),
                    velocity=float(message.velocity),
                )
            )
    return hits, files


def _winsorized(values: list[float], low: float, high: float) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    if not len(data):
        return data
    return np.clip(data, np.quantile(data, low), np.quantile(data, high))


def _mean(values: list[float], fallback: float = 0) -> float:
    data = _winsorized(values, 0.01, 0.99)
    return float(np.mean(data)) if len(data) else fallback


def _std(values: list[float], fallback: float) -> float:
    data = _winsorized(values, 0.02, 0.98)
    return max(fallback, float(np.std(data))) if len(data) >= 2 else fallback


def _centered_component(
    hits: list[Hit], attribute: str, buckets: tuple[str, ...], value: str
) -> dict[str, float]:
    overall = _mean([getattr(hit, value) for hit in hits])
    result = {
        bucket: _mean(
            [getattr(hit, value) for hit in hits if getattr(hit, attribute) == bucket], overall
        )
        - overall
        for bucket in buckets
    }
    weights = {
        bucket: sum(getattr(hit, attribute) == bucket for hit in hits) for bucket in buckets
    }
    center = sum(result[key] * weights[key] for key in buckets) / max(1, sum(weights.values()))
    return {key: result[key] - center for key in buckets}


def _fit_style(name: str, all_hits: list[Hit]) -> dict:
    genres = STYLE_GENRES[name]
    hits = [hit for hit in all_hits if hit.genre in genres]
    position_timing = _centered_component(hits, "position", POSITION_BUCKETS, "timing_us")
    position_velocity = _centered_component(hits, "position", POSITION_BUCKETS, "velocity")
    tempo_timing = _centered_component(hits, "tempo", TEMPO_BUCKETS, "timing_us")
    tempo_velocity = _centered_component(hits, "tempo", TEMPO_BUCKETS, "velocity")
    phrase_timing = _centered_component(hits, "phrase", PHRASE_BUCKETS, "timing_us")
    phrase_velocity = _centered_component(hits, "phrase", PHRASE_BUCKETS, "velocity")

    instrument_means: dict[str, tuple[float, float]] = {}
    for instrument in BASE_VELOCITY:
        selected = [hit for hit in hits if hit.instrument == instrument]
        instrument_means[instrument] = (
            _mean([hit.timing_us for hit in selected]),
            _mean([hit.velocity for hit in selected], BASE_VELOCITY[instrument]),
        )

    residuals: dict[int, tuple[float, float]] = {}
    grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
    for index, hit in enumerate(hits):
        timing_mean, velocity_mean = instrument_means[hit.instrument]
        residuals[index] = (
            hit.timing_us
            - timing_mean
            - position_timing[hit.position]
            - tempo_timing[hit.tempo]
            - phrase_timing[hit.phrase],
            hit.velocity
            - velocity_mean
            - position_velocity[hit.position]
            - tempo_velocity[hit.tempo]
            - phrase_velocity[hit.phrase],
        )
        grouped[(hit.filename, hit.quantized_tick)].append(index)

    peers: dict[int, tuple[float, float]] = {}
    for indexes in grouped.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            others = [residuals[other] for other in indexes if other != index]
            peers[index] = (
                float(np.mean([item[0] for item in others])),
                float(np.mean([item[1] for item in others])),
            )
    shared_timing = _std([item[0] for item in peers.values()], 350)
    shared_velocity = _std([item[1] for item in peers.values()], 0.75)

    instruments: dict[str, dict[str, float | int]] = {}
    for instrument in BASE_VELOCITY:
        indexes = [index for index, hit in enumerate(hits) if hit.instrument == instrument]
        peer_timing = np.asarray([peers[index][0] for index in indexes if index in peers])
        event_timing = np.asarray([residuals[index][0] for index in indexes if index in peers])
        peer_velocity = np.asarray([peers[index][1] for index in indexes if index in peers])
        event_velocity = np.asarray([residuals[index][1] for index in indexes if index in peers])
        timing_loading = (
            float(np.cov(event_timing, peer_timing, ddof=0)[0, 1] / np.var(peer_timing))
            if len(peer_timing) > 2 and np.var(peer_timing) > 1
            else 0.5
        )
        velocity_loading = (
            float(np.cov(event_velocity, peer_velocity, ddof=0)[0, 1] / np.var(peer_velocity))
            if len(peer_velocity) > 2 and np.var(peer_velocity) > 0.01
            else 0.5
        )
        timing_loading = float(np.clip(timing_loading, -1.5, 1.5))
        velocity_loading = float(np.clip(velocity_loading, -1.5, 1.5))
        timing_noise = [
            residuals[index][0] - timing_loading * peers.get(index, (0, 0))[0]
            for index in indexes
        ]
        velocity_noise = [
            residuals[index][1] - velocity_loading * peers.get(index, (0, 0))[1]
            for index in indexes
        ]
        timing_mean, velocity_mean = instrument_means[instrument]
        instruments[instrument] = {
            "count": len(indexes),
            "timing_mean_us": float(np.clip(timing_mean, -25_000, 25_000)),
            "timing_residual_std_us": min(25_000, _std(timing_noise, 500)),
            "velocity_mean": float(np.clip(velocity_mean, 1, 127)),
            "velocity_residual_std": min(50, _std(velocity_noise, 1)),
            "timing_loading": timing_loading,
            "velocity_loading": velocity_loading,
        }
    kick = instruments["kick"]
    instruments["bass"] = {
        **kick,
        "timing_mean_us": float(np.clip(float(kick["timing_mean_us"]) + 3_500, -25_000, 25_000)),
        "velocity_mean": float(np.clip(float(kick["velocity_mean"]) - 4, 1, 127)),
    }
    return {
        "source_genres": sorted(genres),
        "hit_count": len(hits),
        "shared_timing_std_us": min(25_000, shared_timing),
        "shared_velocity_std": min(50, shared_velocity),
        "instruments": instruments,
        "position_timing_us": position_timing,
        "position_velocity": position_velocity,
        "tempo_timing_us": tempo_timing,
        "tempo_velocity": tempo_velocity,
        "phrase_timing_us": phrase_timing,
        "phrase_velocity": phrase_velocity,
    }


def _predict(model: dict, hit: Hit) -> tuple[float, float]:
    style = GENRE_STYLE.get(hit.genre, "Balanced")
    profile = model["styles"][style]
    instrument = profile["instruments"][hit.instrument]
    timing = (
        instrument["timing_mean_us"]
        + profile["position_timing_us"][hit.position]
        + profile["tempo_timing_us"][hit.tempo]
        + profile["phrase_timing_us"][hit.phrase]
    )
    velocity = (
        instrument["velocity_mean"]
        + profile["position_velocity"][hit.position]
        + profile["tempo_velocity"][hit.tempo]
        + profile["phrase_velocity"][hit.phrase]
    )
    return timing, velocity


def train(dataset_root: Path) -> PerformanceModel:
    train_hits, train_files = _read_hits(dataset_root, "train")
    validation_hits, validation_files = _read_hits(dataset_root, "validation")
    payload: dict = {
        "schema_version": "1.0",
        "model_id": "gmd-performance-v1",
        "model_version": "1.0.0",
        "dataset": {
            "name": "Groove MIDI Dataset v1.0.0 MIDI-only",
            "license": "CC BY 4.0",
            "attribution": "Google LLC; Gillick et al., ICML 2019",
            "source_url": DATASET_URL,
            "sha256": DATASET_SHA256,
            "training_split": "train beats in 4/4",
            "training_files": train_files,
            "training_hits": len(train_hits),
        },
        "styles": {name: _fit_style(name, train_hits) for name in STYLE_GENRES},
        "validation": {},
    }
    learned = [_predict(payload, hit) for hit in validation_hits]
    payload["validation"] = {
        "split": "validation beats in 4/4",
        "files": validation_files,
        "hits": len(validation_hits),
        "timing_mae_us_rule_zero": float(np.mean([abs(hit.timing_us) for hit in validation_hits])),
        "timing_mae_us_learned_mean": float(
            np.mean(
                [
                    abs(hit.timing_us - prediction[0])
                    for hit, prediction in zip(validation_hits, learned, strict=True)
                ]
            )
        ),
        "velocity_mae_rule_fixed": float(
            np.mean([abs(hit.velocity - BASE_VELOCITY[hit.instrument]) for hit in validation_hits])
        ),
        "velocity_mae_learned_mean": float(
            np.mean(
                [
                    abs(hit.velocity - prediction[1])
                    for hit, prediction in zip(validation_hits, learned, strict=True)
                ]
            )
        ),
    }
    return PerformanceModel.model_validate(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the Human Groove performance model")
    parser.add_argument(
        "dataset_root", type=Path, help="Extracted groove directory containing info.csv"
    )
    parser.add_argument("output", type=Path, help="Destination model JSON")
    arguments = parser.parse_args()
    model = train(arguments.dataset_root)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {model.model_id} from {model.dataset['training_hits']} hits; "
        f"validation={model.validation['hits']} hits"
    )


if __name__ == "__main__":
    main()
