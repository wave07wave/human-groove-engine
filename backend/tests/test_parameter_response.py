from statistics import mean

from conftest import intent, meter

from app.analysis.listener import analyze_pattern
from app.engine.generator import generate_pattern


def measured(seed: int, **values: float):
    pattern = generate_pattern(bpm=108, bars=4, meter=meter(), intent=intent(**values), seed=seed)
    return analyze_pattern(pattern)


def test_syncopation_target_moves_measured_syncopation_over_32_seeds():
    low = mean(measured(seed, syncopation=0.05).measured_dna.syncopation for seed in range(32))
    high = mean(measured(seed, syncopation=0.95).measured_dna.syncopation for seed in range(32))
    assert high > low + 0.025


def test_stability_target_improves_beat_confidence_over_32_seeds():
    low = mean(measured(seed, pulse_stability=0.05).listener.beat_confidence for seed in range(32))
    high = mean(measured(seed, pulse_stability=0.95).listener.beat_confidence for seed in range(32))
    assert high > low


def test_interlock_target_improves_relationship_fit():
    low = mean(measured(seed, interlock=0.05).measured_dna.interlock for seed in range(32))
    high = mean(measured(seed, interlock=0.95).measured_dna.interlock for seed in range(32))
    assert high > low
