from __future__ import annotations

import math

from app.analysis.listener import analyze_pattern
from app.audio import analyze_reference_render
from app.models.evaluation import MotorTempoProfile
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.models.pattern import GroovePattern
from app.models.preference import GroovePreferenceSummary
from app.preference import PREFERENCE_FEATURES, blended_candidate_score, personal_preference_score
from app.preference_guidance import PreferenceGuidance, guided_feature_values

from .generator import generate_pattern


def pattern_distance(a: GroovePattern, b: GroovePattern) -> float:
    left = {(e.instrument.value, e.grid_tick, e.primary_role.value) for e in a.events}
    right = {(e.instrument.value, e.grid_tick, e.primary_role.value) for e in b.events}
    event_distance = 1 - len(left & right) / max(1, len(left | right))
    adna = a.analysis.measured_dna.model_dump() if a.analysis else {}
    bdna = b.analysis.measured_dna.model_dump() if b.analysis else {}
    dna_distance = sum(abs(adna[k] - bdna[k]) for k in adna) / max(1, len(adna))
    return 0.75 * event_distance + 0.25 * dna_distance


def preference_guided_groove_intent(
    intent: GrooveIntent, preference: GroovePreferenceSummary | None
) -> tuple[GrooveIntent, PreferenceGuidance]:
    guidance = guided_feature_values(
        intent.target_dna.model_dump(),
        {feature: feature for feature in PREFERENCE_FEATURES},
        preference,
    )
    guided = intent.model_copy(deep=True)
    for feature, value in guidance.values.items():
        setattr(guided.target_dna, feature, value)
    return guided, guidance


def generate_candidate_pool(
    *,
    bpm: float,
    bars: int,
    meter: MeterDefinition,
    intent: GrooveIntent,
    seed: int,
    mode: str = "preview",
    performance_mode: str = "auto",
    render_profile: str = "studio-tight-v1",
    preset: str = "Balanced",
    preference: GroovePreferenceSummary | None = None,
    motor_tempo_profile: MotorTempoProfile | None = None,
    embodied_operator_scores: dict[str, float] | None = None,
) -> list[GroovePattern]:
    pool_size = 16 if mode == "preview" else 64
    guided_intent, guidance = preference_guided_groove_intent(intent, preference)
    pool: list[GroovePattern] = []
    for candidate in range(pool_size):
        use_guidance = guidance.active and candidate % 2 == 1
        # Stratify the research candidates around low / medium / high challenge.
        # These are exploration arms, not a claim that one level suits everyone.
        candidate_intent = (guided_intent if use_guidance else intent).model_copy(deep=True)
        challenge_arm = (0.24, 0.5, 0.76)[candidate % 3]
        candidate_intent.embodied.challenge = challenge_arm
        candidate_intent.embodied.renewal = (0.3, 0.58, 0.78)[candidate % 3]
        pattern = generate_pattern(
            bpm=bpm,
            bars=bars,
            meter=meter,
            intent=candidate_intent,
            seed=seed,
            candidate=candidate,
            name=f"{preset} · {chr(65 + candidate)}",
            style=preset,
            performance_mode=performance_mode,
            render_profile=render_profile,
        )
        # Candidate arms are a generation intervention, not a mutation of the
        # user's requested Intent or their stored preference evidence.
        pattern.intent = intent.model_copy(deep=True)
        if use_guidance:
            pattern.metadata.preference_guided = True
            pattern.metadata.preference_guidance_strength = guidance.strength
            pattern.metadata.preference_guided_features = list(guidance.features)
        pattern.analysis = analyze_pattern(pattern, include_render=False)
        pool.append(pattern)
    return pool


def generate_candidates(
    *,
    bpm: float,
    bars: int,
    meter: MeterDefinition,
    intent: GrooveIntent,
    seed: int,
    count: int = 4,
    mode: str = "preview",
    performance_mode: str = "auto",
    render_profile: str = "studio-tight-v1",
    preset: str = "Balanced",
    preference: GroovePreferenceSummary | None = None,
    motor_tempo_profile: MotorTempoProfile | None = None,
    embodied_operator_scores: dict[str, float] | None = None,
) -> list[GroovePattern]:
    pool = generate_candidate_pool(
        bpm=bpm,
        bars=bars,
        meter=meter,
        intent=intent,
        seed=seed,
        mode=mode,
        performance_mode=performance_mode,
        render_profile=render_profile,
        preset=preset,
        preference=preference,
        motor_tempo_profile=motor_tempo_profile,
        embodied_operator_scores=embodied_operator_scores,
    )

    render_pool_size = min(len(pool), 6 if mode == "preview" else 12)
    ordered = sorted(pool, key=lambda item: blended_candidate_score(item, preference), reverse=True)
    render_pool = [ordered.pop(0)]
    while ordered and len(render_pool) < render_pool_size:
        candidate = max(
            ordered,
            key=lambda item: 0.8 * blended_candidate_score(item, preference)
            + 0.2 * min(pattern_distance(item, chosen) for chosen in render_pool),
        )
        render_pool.append(candidate)
        ordered.remove(candidate)
    for item in render_pool:
        item.analysis.rendered_audio = analyze_reference_render(item)
    pool = render_pool

    def rendered_score(item: GroovePattern) -> float:
        if item.analysis and item.analysis.rendered_audio:
            return item.analysis.rendered_audio.render_quality
        return 0.5

    def selection_score(item: GroovePattern) -> float:
        arm_score = (embodied_operator_scores or {}).get(item.metadata.embodied_operator_arm, 0.5)
        return (
            0.84 * blended_candidate_score(item, preference)
            + 0.1 * rendered_score(item)
            + 0.06 * arm_score
        )

    tempo_fit = 0.5
    if motor_tempo_profile and motor_tempo_profile.confidence >= 0.35:
        nearest = min(abs(math.log2(bpm / alias)) for alias in motor_tempo_profile.tempo_aliases)
        tempo_fit = max(0.0, 1 - nearest / 1.2) * motor_tempo_profile.confidence + 0.5 * (
            1 - motor_tempo_profile.confidence
        )

    def objective_vector(item: GroovePattern) -> tuple[float, float, float, float, float]:
        analysis = item.analysis
        return (
            1 - analysis.intent_loss if analysis else 0,
            analysis.listener.predicted_groove if analysis else 0,
            personal_preference_score(item, preference),
            rendered_score(item),
            tempo_fit,
        )

    def dominates(left: GroovePattern, right: GroovePattern) -> bool:
        a, b = objective_vector(left), objective_vector(right)
        return all(x >= y for x, y in zip(a, b, strict=True)) and any(
            x > y for x, y in zip(a, b, strict=True)
        )

    frontier = [item for item in pool if not any(dominates(other, item) for other in pool)]
    remainder = [item for item in pool if item not in frontier]
    frontier.sort(key=selection_score, reverse=True)
    remainder.sort(key=selection_score, reverse=True)
    pool = frontier + remainder
    selected = [pool.pop(0)]
    while pool and len(selected) < count:
        candidate = max(
            pool,
            key=lambda item: 0.74 * selection_score(item)
            + 0.26 * min(pattern_distance(item, chosen) for chosen in selected),
        )
        selected.append(candidate)
        pool.remove(candidate)
    for index, item in enumerate(selected):
        item.name = f"{preset} · {chr(65 + index)}"
    return selected
