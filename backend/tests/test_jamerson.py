from __future__ import annotations

import hashlib
import json
from io import BytesIO
from statistics import mean, pstdev

import mido
import pytest
from fastapi.testclient import TestClient

from app.bass.generation import generate_bass_pattern
from app.bass.midi import export_bass_midi
from app.bass.models import (
    BassGenerateRequest,
    BassPattern,
    MotownBassSettings,
    MutationOperation,
)
from app.bass.motown import jamerson_profile_for_bpm
from app.bass.mutation import mutate_bass_pattern
from app.bass.persistence import BassDatabase
from app.main import app

HARMONY = "C | Am7 | F | G7 | C | Am7 | Dm7 | G7"


def _generated(mode: str, seed: int, *, bpm: float = 100) -> BassPattern:
    return generate_bass_pattern(
        BassGenerateRequest(
            bars=8,
            seed=seed,
            bpm=bpm,
            harmony=HARMONY,
            motown_bass=MotownBassSettings(mode=mode),
        )
    )


def _summary(patterns: list[BassPattern]) -> dict[str, float]:
    return {
        "notes_per_bar": mean(len(pattern.events) / pattern.bars for pattern in patterns),
        "syncopation": mean(pattern.analysis.atomic.syncopation_index for pattern in patterns),
        "chromatic": mean(pattern.analysis.atomic.chromatic_ratio for pattern in patterns),
        "motion": mean(pattern.analysis.dna.melodic_motion for pattern in patterns),
        "ghost": mean(
            sum(event.rhythmic_role.value == "ghost" for event in pattern.events)
            / len(pattern.events)
            for pattern in patterns
        ),
        "mute": mean(
            sum(event.articulation.technique.value == "mute" for event in pattern.events)
            / len(pattern.events)
            for pattern in patterns
        ),
        "velocity_spread": mean(
            pstdev(event.velocity for event in pattern.events) for pattern in patterns
        ),
        "timing_spread": mean(
            pstdev(event.micro_offset_us for event in pattern.events)
            for pattern in patterns
        ),
        "phrase_development": mean(
            pattern.analysis.dna.phrase_development for pattern in patterns
        ),
        "resolution": mean(pattern.analysis.dna.resolution_strength for pattern in patterns),
    }


def test_standard_bass_generation_snapshot_is_unchanged() -> None:
    pattern = generate_bass_pattern(BassGenerateRequest(bars=4, seed=42, candidate_count=1))
    payload = {
        "events": [event.model_dump(mode="json") for event in pattern.events],
        "structural_events": [
            event.model_dump(mode="json") for event in pattern.structural_events
        ],
        "analysis": pattern.analysis.model_dump(mode="json"),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()

    assert digest == "5960bd0f5f1e800b7a6c7e760b22247a29a1ecedb4c19f733340b0237911f327"
    assert pattern.metadata.motown_bass.mode == "standard"


def test_jamerson_generation_is_deterministic_but_not_a_fixed_phrase() -> None:
    request = BassGenerateRequest(
        bars=8,
        seed=8172,
        harmony=HARMONY,
        motown_bass=MotownBassSettings(mode="jamerson"),
    )
    left = generate_bass_pattern(request, candidate=2)
    right = generate_bass_pattern(request, candidate=2)
    assert left.model_dump_json() == right.model_dump_json()

    signatures = {
        tuple(
            (
                event.grid_tick,
                event.pitch,
                event.velocity,
                event.micro_offset_us,
                event.duration_tick,
            )
            for event in _generated("jamerson", seed).events
        )
        for seed in range(10, 20)
    }
    assert len(signatures) == 10


def test_jamerson_style_has_statistically_distinct_bass_language() -> None:
    standard = _summary([_generated("standard", seed) for seed in range(30, 50)])
    jamerson = _summary([_generated("jamerson", seed) for seed in range(30, 50)])

    assert jamerson["notes_per_bar"] > standard["notes_per_bar"] + 0.7
    assert jamerson["syncopation"] > standard["syncopation"] + 0.03
    assert jamerson["chromatic"] > standard["chromatic"] + 0.01
    assert jamerson["motion"] > standard["motion"] + 0.06
    assert standard["ghost"] == 0
    assert jamerson["ghost"] > 0.08
    assert standard["mute"] == 0
    assert jamerson["mute"] > 0.45
    assert jamerson["velocity_spread"] > standard["velocity_spread"] + 8
    assert jamerson["timing_spread"] > standard["timing_spread"] + 400
    assert jamerson["phrase_development"] > standard["phrase_development"] + 0.08
    assert jamerson["resolution"] > standard["resolution"] + 0.025


def test_jamerson_bpm_compensation_reduces_ornamentation_at_fast_tempos() -> None:
    medium = jamerson_profile_for_bpm(100)
    fast = jamerson_profile_for_bpm(170)
    assert fast.density < medium.density
    assert fast.syncopation < medium.syncopation
    assert fast.chromaticism < medium.chromaticism
    assert fast.ghost_probability < medium.ghost_probability
    assert fast.timing_spread_us < medium.timing_spread_us

    medium_patterns = [_generated("jamerson", seed, bpm=100) for seed in range(8)]
    fast_patterns = [_generated("jamerson", seed, bpm=170) for seed in range(8)]
    assert mean(len(pattern.events) for pattern in fast_patterns) < mean(
        len(pattern.events) for pattern in medium_patterns
    )


def test_jamerson_style_respects_chromatic_opt_out() -> None:
    request = BassGenerateRequest(
        bars=8,
        seed=91,
        harmony=HARMONY,
        motown_bass=MotownBassSettings(mode="jamerson"),
    )
    request.intent.allow_chromatic_notes = False
    request.intent.target.chromaticism = 1
    pattern = generate_bass_pattern(request)
    assert pattern.analysis.atomic.chromatic_ratio == 0


def test_jamerson_setting_survives_mutation_history_and_old_payloads(tmp_path) -> None:
    pattern = _generated("jamerson", 661)
    mutated = mutate_bass_pattern(pattern, {0}, MutationOperation.REGENERATE)
    assert mutated.metadata.motown_bass.mode == "jamerson"

    database = BassDatabase(tmp_path / "jamerson-history.db")
    database.save_generation(mutated)
    restored = database.generation_pattern(mutated.pattern_id)
    assert restored is not None
    assert restored.metadata.motown_bass.mode == "jamerson"

    legacy = pattern.model_dump(mode="json")
    legacy["metadata"].pop("motown_bass")
    assert BassPattern.model_validate(legacy).metadata.motown_bass.mode == "standard"


def test_jamerson_api_and_midi_metadata_contract() -> None:
    client = TestClient(app)
    capabilities = client.get("/api/v1/bass/capabilities").json()
    assert capabilities["motown_bass_styles"] == ["standard", "jamerson"]
    assert capabilities["jamerson_inspired_generation"] is True

    response = client.post(
        "/api/v1/bass/generate",
        json={
            "bars": 4,
            "harmony": "C | Am7 | F | G7",
            "candidate_count": 1,
            "seed": 705,
            "motown_bass": {"mode": "jamerson"},
        },
    )
    assert response.status_code == 200, response.text
    candidate = response.json()["candidates"][0]
    assert candidate["metadata"]["motown_bass"] == {"mode": "jamerson"}

    midi = mido.MidiFile(file=BytesIO(export_bass_midi(BassPattern.model_validate(candidate))))
    text = " ".join(
        message.text
        for track in midi.tracks
        for message in track
        if message.type == "text"
    )
    assert "motown_bass=jamerson" in text


@pytest.mark.parametrize("preset", ["Supportive", "Walking", "Syncopated"])
def test_jamerson_layer_is_independent_of_bass_preset(preset: str) -> None:
    pattern = generate_bass_pattern(
        BassGenerateRequest(
            bars=4,
            seed=1001,
            harmony="C | Am7 | F | G7",
            preset=preset,
            motown_bass=MotownBassSettings(mode="jamerson"),
        )
    )
    assert pattern.metadata.preset == preset
    assert pattern.metadata.motown_bass.mode == "jamerson"
    assert any(event.articulation.technique.value == "mute" for event in pattern.events)
