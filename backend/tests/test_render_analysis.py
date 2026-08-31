from conftest import intent, meter

from app.analysis.listener import analyze_pattern
from app.audio.render_analysis import (
    analyze_reference_render,
    available_render_profiles,
    load_render_profile,
    reference_velocity_gain,
)
from app.engine.generator import generate_pattern
from app.engine.optimizer import generate_candidates
from app.models.event import InstrumentID


def pattern(*, bars: int = 2, profile: str = "studio-tight-v1"):
    return generate_pattern(
        bpm=100,
        bars=bars,
        meter=meter(),
        intent=intent(),
        seed=64,
        render_profile=profile,
    )


def test_profiles_are_versioned_complete_and_discoverable():
    identifiers = {item["profile_id"] for item in available_render_profiles()}
    assert identifiers == {
        "studio-tight-v1",
        "warm-pocket-v1",
        "club-punch-v1",
        "vintage-dust-v1",
    }
    for identifier in identifiers:
        profile = load_render_profile(identifier)
        assert profile is not None and profile.version == "1.0.0"
        assert {instrument.value for instrument in InstrumentID}.issubset(profile.instruments)
    assert load_render_profile("../studio-tight-v1") is None


def test_reference_render_is_deterministic_and_can_be_disabled():
    rendered = pattern()
    assert analyze_reference_render(rendered) == analyze_reference_render(rendered)
    assert analyze_pattern(rendered, include_render=True).rendered_audio is not None
    disabled = pattern(profile="off")
    assert analyze_pattern(disabled, include_render=True).rendered_audio is None


def test_reference_render_uses_the_acoustic_preview_velocity_curve():
    assert reference_velocity_gain(0) == 0
    assert reference_velocity_gain(127) == 1
    assert reference_velocity_gain(64) == (64 / 127) ** 1.25
    assert reference_velocity_gain(64) < 64 / 127


def test_low_end_collision_responds_to_performed_overlap():
    source = pattern(bars=1)
    kick = next(event for event in source.events if event.instrument == InstrumentID.KICK)
    bass = kick.model_copy(
        update={"event_id": "bass-overlap", "instrument": InstrumentID.BASS, "pitch": 36}
    )
    overlapping = source.model_copy(update={"events": [kick, bass]})
    separated = source.model_copy(
        update={"events": [kick, bass.model_copy(update={"grid_tick": 2 * 960})]}
    )
    overlap_analysis = analyze_reference_render(overlapping)
    separated_analysis = analyze_reference_render(separated)
    assert overlap_analysis.low_end_collision_applicable
    assert overlap_analysis.low_end_collision > separated_analysis.low_end_collision


def test_long_form_analysis_samples_the_complete_phrase():
    analysis = analyze_reference_render(pattern(bars=64))
    assert len(analysis.analyzed_bars) == 8
    assert analysis.analyzed_bars[0] == 0
    assert analysis.analyzed_bars[-1] == 63


def test_every_selected_candidate_has_reference_render_metrics():
    candidates = generate_candidates(
        bpm=102,
        bars=2,
        meter=meter(),
        intent=intent(),
        seed=78,
    )
    assert len(candidates) == 4
    assert all(candidate.analysis.rendered_audio is not None for candidate in candidates)
    assert all(
        0 <= candidate.analysis.rendered_audio.render_quality <= 1 for candidate in candidates
    )
