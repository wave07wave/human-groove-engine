import json

from conftest import intent, meter

from app.engine.generator import generate_pattern
from app.engine.mutation import regenerate_selected
from app.engine.performance import (
    load_performance_model,
    performance_adjustment,
)
from app.models.event import InstrumentID
from app.random.seeds import HierarchicalRNG


def test_bundled_model_has_provenance_and_held_out_improvement():
    model = load_performance_model()
    assert model is not None
    assert model.dataset["license"] == "CC BY 4.0"
    assert model.dataset["training_hits"] == 324852
    assert model.validation["timing_mae_us_learned_mean"] < model.validation[
        "timing_mae_us_rule_zero"
    ]
    assert model.validation["velocity_mae_learned_mean"] < model.validation[
        "velocity_mae_rule_fixed"
    ]


def test_invalid_or_missing_model_falls_back_without_raising(tmp_path):
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text(json.dumps({"schema_version": "99"}), encoding="utf-8")
    assert load_performance_model(missing) is None
    assert load_performance_model(malformed) is None


def test_learned_mode_is_deterministic_and_preserves_score_grid():
    arguments = {
        "bpm": 108,
        "bars": 4,
        "meter": meter(),
        "intent": intent(microtiming=0.8),
        "seed": 813,
        "style": "Funk",
    }
    learned = generate_pattern(**arguments)
    repeated = generate_pattern(**arguments)
    rule = generate_pattern(**arguments, performance_mode="rule")
    def score(pattern):
        return [
            (event.instrument, event.grid_tick, event.primary_role) for event in pattern.events
        ]
    assert learned.model_dump_json() == repeated.model_dump_json()
    assert score(learned) == score(rule)
    assert learned.metadata.performance_model == "gmd-performance-v1"
    assert rule.metadata.performance_model == "rule-pocket-v1"
    assert [event.micro_offset_us for event in learned.events] != [
        event.micro_offset_us for event in rule.events
    ]


def test_simultaneous_instruments_share_learned_timing_latent():
    model = load_performance_model().model_copy(deep=True)
    profile = model.styles["Balanced"]
    profile.shared_timing_std_us = 1_000
    profile.position_timing_us = dict.fromkeys(profile.position_timing_us, 0)
    profile.tempo_timing_us = dict.fromkeys(profile.tempo_timing_us, 0)
    profile.phrase_timing_us = dict.fromkeys(profile.phrase_timing_us, 0)
    for instrument in profile.instruments.values():
        instrument.timing_mean_us = 0
        instrument.timing_residual_std_us = 0
        instrument.timing_loading = 1
    common = {
        "model": model,
        "hrng": HierarchicalRNG(91),
        "style": "Balanced",
        "bpm": 100,
        "bar": 0,
        "bars": 4,
        "slot": 4,
        "subdivisions_per_quarter": 4,
        "candidate": 2,
    }
    kick = performance_adjustment(instrument=InstrumentID.KICK, **common)
    snare = performance_adjustment(instrument=InstrumentID.SNARE, **common)
    later = performance_adjustment(instrument=InstrumentID.KICK, **{**common, "slot": 5})
    assert kick.timing_us == snare.timing_us
    assert kick.timing_us != later.timing_us


def test_partial_regeneration_records_a_rule_fallback(monkeypatch):
    pattern = generate_pattern(
        bpm=100,
        bars=2,
        meter=meter(),
        intent=intent(),
        seed=52,
    )
    monkeypatch.setattr("app.engine.generator.load_performance_model", lambda: None)
    changed = regenerate_selected(pattern, {InstrumentID.SNARE}, {1})
    assert changed.metadata.performance_model == "mixed:gmd-performance-v1+rule-pocket-v1"
