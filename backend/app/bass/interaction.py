from __future__ import annotations

from copy import deepcopy
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.analysis.listener import analyze_pattern
from app.audio import analyze_reference_render
from app.config import PPQ
from app.engine.generator import generate_pattern
from app.models.analysis import RenderedAudioAnalysis
from app.models.event import InstrumentID
from app.models.pattern import GroovePattern

from .analysis import analyze_bass_pattern, clamp
from .explain import attach_decision_traces
from .generation import (
    generate_bass_candidates,
    generate_preference_search_bass_pattern,
)
from .integration import groove_context_from_pattern
from .models import (
    BassGenerateRequest,
    BassPattern,
    BassPreferenceSummary,
    RhythmBassInteractionDNA,
)
from .preference import blended_candidate_score


class IntegrationMode(StrEnum):
    FOLLOW = "follow"
    NEGOTIATE = "negotiate"
    CO_CREATE = "co_create"


class JointGenerateRequest(BaseModel):
    groove_pattern: GroovePattern
    bass_request: BassGenerateRequest
    mode: IntegrationMode = IntegrationMode.FOLLOW
    shared_complexity_budget: float = Field(0.55, ge=0, le=1)
    bass_complexity_share: float = Field(0.60, ge=0, le=1)
    candidate_count: int = Field(4, ge=1, le=4)
    reference_render_analysis: bool = False

    @model_validator(mode="after")
    def matching_structure(self) -> "JointGenerateRequest":
        if self.bass_request.meter != self.groove_pattern.meter:
            raise ValueError("joint generation requires matching meters")
        if self.bass_request.bars != self.groove_pattern.bars:
            raise ValueError("joint generation requires matching output lengths")
        return self


class JointChange(BaseModel):
    target: str
    event_id: str | None = None
    operation: str
    tick_before: int | None = None
    tick_after: int | None = None
    reason: str


class JointGenerationResult(BaseModel):
    groove_pattern: GroovePattern
    bass_pattern: BassPattern
    interaction: RhythmBassInteractionDNA
    joint_fitness: float
    change_cost: float
    complexity_fit: float
    rendered_audio: RenderedAudioAnalysis | None = None
    changes: list[JointChange] = Field(default_factory=list)


class JointGenerateResponse(BaseModel):
    mode: IntegrationMode
    candidates: list[JointGenerationResult]


def _aligned_request(request: JointGenerateRequest, groove: GroovePattern) -> BassGenerateRequest:
    intent = request.bass_request.intent.model_copy(deep=True)
    bass_target = request.shared_complexity_budget * request.bass_complexity_share
    intent.target.density = clamp(0.62 * intent.target.density + 0.38 * bass_target)
    intent.target.syncopation = clamp(0.72 * intent.target.syncopation + 0.28 * bass_target)
    intent.target.melodic_motion = clamp(
        0.78 * intent.target.melodic_motion + 0.22 * bass_target
    )
    intent.target.silence = clamp(0.72 * intent.target.silence + 0.28 * (1 - bass_target))
    return request.bass_request.model_copy(
        update={
            "bpm": groove.bpm,
            "bars": groove.bars,
            "meter": groove.meter,
            "groove_context": groove_context_from_pattern(groove),
            "intent": intent,
        }
    )


def _kick_complexity(groove: GroovePattern) -> float:
    kicks = [event for event in groove.events if event.instrument == InstrumentID.KICK]
    slots = groove.bars * groove.meter.bar_ticks / (PPQ // 4)
    density = clamp(len(kicks) / max(1, slots) * 2.5)
    weak = sum(event.grid_tick % PPQ != 0 for event in kicks) / max(1, len(kicks))
    return clamp(0.65 * density + 0.35 * weak)


def _phrase_complexity_targets(bars: int, overall: float) -> list[float]:
    # Establish → develop → peak → recover. The same contour repeats for long form output.
    contour = (0.72, 1.04, 1.18, 0.62)
    return [clamp(overall * contour[bar % len(contour)]) for bar in range(bars)]


def _apply_phrase_complexity_to_bass(
    bass: BassPattern, targets: list[float]
) -> BassPattern:
    result = deepcopy(bass)
    selected_ids: set[str] = set()
    approach_targets = {
        event.approach_target_id for event in result.events if event.approach_target_id
    }
    for bar, target in enumerate(targets):
        events = [
            event
            for event in result.events
            if event.grid_tick // result.meter.bar_ticks == bar
        ]
        if not events:
            continue
        protected = {
            event.event_id
            for event in events
            if event.rhythmic_role.value in {"anchor", "recovery"}
            or event.event_id in approach_targets
        }
        wanted = max(len(protected), round(len(events) * (0.58 + 0.72 * target)))
        ranked = sorted(
            events,
            key=lambda event: (event.event_id in protected, event.structural_weight),
            reverse=True,
        )
        selected_ids.update(event.event_id for event in ranked[:wanted])
    selected_events = [
        event for event in result.events if event.event_id in selected_ids
    ]
    valid_ids = {event.event_id for event in selected_events}
    selected_events = [
        event
        for event in selected_events
        if not event.approach_target_id or event.approach_target_id in valid_ids
    ]
    valid_ids = {event.event_id for event in selected_events}
    structural_events = [
        event.model_copy(
            update={"target_event_id": None}
            if event.target_event_id and event.target_event_id not in valid_ids
            else {}
        )
        for event in result.structural_events
    ]
    payload = result.model_dump()
    payload["events"] = [event.model_dump() for event in selected_events]
    payload["structural_events"] = [event.model_dump() for event in structural_events]
    return BassPattern.model_validate(payload)


def _bass_complexity(bass: BassPattern) -> float:
    if not bass.analysis:
        bass.analysis = analyze_bass_pattern(bass)
    atomic = bass.analysis.atomic
    return clamp(
        0.42 * atomic.onset_density * 1.8
        + 0.24 * atomic.syncopation_index
        + 0.18 * atomic.chromatic_ratio
        + 0.16 * clamp(atomic.register_span / 24)
    )


def _interaction_quality(interaction: RhythmBassInteractionDNA) -> float:
    return clamp(
        0.23 * interaction.kick_bass_lock
        + 0.14 * interaction.kick_bass_complement
        + 0.10 * interaction.kick_bass_answer
        + 0.08 * interaction.kick_bass_anticipation
        + 0.12 * interaction.perceived_phase_coherence
        + 0.12 * interaction.low_end_complexity_balance
        + 0.11 * interaction.shared_recovery
        + 0.10 * interaction.pulse_reinforcement
    )


def _complexity_fit(
    groove: GroovePattern,
    bass: BassPattern,
    budget: float,
    bass_share: float,
) -> float:
    wanted_bass = budget * bass_share
    wanted_kick = budget * (1 - bass_share)
    distance = abs(_bass_complexity(bass) - wanted_bass) + abs(
        _kick_complexity(groove) - wanted_kick
    )
    return clamp(1 - distance / 1.35)


def _make_result(
    request: JointGenerateRequest,
    groove: GroovePattern,
    bass: BassPattern,
    changes: list[JointChange],
    change_cost: float,
    preference: BassPreferenceSummary | None = None,
) -> JointGenerationResult:
    groove_analysis = groove.analysis or analyze_pattern(groove)
    if groove.pattern_id != request.groove_pattern.pattern_id:
        groove.analysis = groove_analysis
    bass.groove_context = groove_context_from_pattern(groove)
    attach_decision_traces(bass)
    bass.analysis = analyze_bass_pattern(bass)
    interaction = bass.interaction_analysis
    if interaction is None:
        raise ValueError("joint generation requires Kick context")
    complexity = _complexity_fit(
        groove,
        bass,
        request.shared_complexity_budget,
        request.bass_complexity_share,
    )
    groove_fitness = groove_analysis.fitness
    bass_fitness = blended_candidate_score(bass, preference)
    fitness = (
        0.42 * bass_fitness
        + 0.25 * groove_fitness
        + 0.23 * _interaction_quality(interaction)
        + 0.10 * complexity
        - change_cost
    )
    return JointGenerationResult(
        groove_pattern=groove,
        bass_pattern=bass,
        interaction=interaction,
        joint_fitness=fitness,
        change_cost=change_cost,
        complexity_fit=complexity,
        changes=changes,
    )


def _follow(
    request: JointGenerateRequest, preference: BassPreferenceSummary | None = None
) -> list[JointGenerationResult]:
    aligned = _aligned_request(request, request.groove_pattern)
    aligned.candidate_count = request.candidate_count
    return [
        _make_result(request, deepcopy(request.groove_pattern), bass, [], 0, preference)
        for bass in generate_bass_candidates(aligned, preference)
    ]


def _negotiated_variant(
    request: JointGenerateRequest, bass: BassPattern
) -> tuple[GroovePattern, list[JointChange]]:
    source = request.groove_pattern
    result = deepcopy(source)
    if InstrumentID.KICK in source.instrument_locks:
        return result, []
    bass_ticks = [event.performed_tick for event in bass.events]
    candidates: list[tuple[int, int, int]] = []
    for index, kick in enumerate(result.events):
        bar = kick.grid_tick // result.meter.bar_ticks
        if (
            kick.instrument != InstrumentID.KICK
            or kick.locked
            or kick.origin == "user_edited"
            or bar in result.bar_locks
        ):
            continue
        if any(abs(kick.performed_tick - tick) <= 80 for tick in bass_ticks):
            continue
        nearest = min(bass_ticks, key=lambda tick: abs(tick - kick.performed_tick), default=None)
        if nearest is not None and abs(nearest - kick.performed_tick) <= PPQ // 4:
            candidates.append((abs(nearest - kick.performed_tick), index, nearest))
    if not candidates:
        return result, []
    _, index, target_tick = min(candidates)
    kick = result.events[index]
    before = kick.performed_tick
    kick.structural_offset_tick += target_tick - before
    result.pattern_id = f"{source.pattern_id}-neg-{kick.event_id[-6:]}"
    result.analysis = None
    return result, [
        JointChange(
            target="kick",
            event_id=kick.event_id,
            operation="align_onset",
            tick_before=before,
            tick_after=target_tick,
            reason="smallest Kick move improving Bass interaction",
        )
    ]


def _negotiate(
    request: JointGenerateRequest, preference: BassPreferenceSummary | None = None
) -> list[JointGenerationResult]:
    aligned = _aligned_request(request, request.groove_pattern)
    aligned.candidate_count = request.candidate_count
    bass_candidates = generate_bass_candidates(aligned, preference)
    results: list[JointGenerationResult] = []
    kick_count = sum(
        event.instrument == InstrumentID.KICK for event in request.groove_pattern.events
    )
    for bass in bass_candidates:
        baseline = _make_result(
            request, deepcopy(request.groove_pattern), deepcopy(bass), [], 0, preference
        )
        results.append(baseline)
        repaired_groove, changes = _negotiated_variant(request, bass)
        if changes:
            cost = 0.035 + 0.08 / max(1, kick_count)
            repaired_bass = deepcopy(bass)
            repaired = _make_result(
                request, repaired_groove, repaired_bass, changes, cost, preference
            )
            if repaired.joint_fitness > baseline.joint_fitness:
                results.append(repaired)
    results.sort(key=lambda item: item.joint_fitness, reverse=True)
    return results[: request.candidate_count]


def _kick_signature(pattern: GroovePattern) -> set[tuple[int, int, int]]:
    return {
        (event.grid_tick, event.structural_offset_tick, event.velocity)
        for event in pattern.events
        if event.instrument == InstrumentID.KICK
    }


def _co_created_groove(
    source: GroovePattern, candidate: int, kick_targets: list[float]
) -> tuple[GroovePattern, list[JointChange], float]:
    if InstrumentID.KICK in source.instrument_locks:
        return deepcopy(source), [], 0
    groove_intent = source.intent.model_copy(deep=True)
    kick_target = sum(kick_targets) / max(1, len(kick_targets))
    groove_intent.target_dna.low_end_anchor = clamp(
        0.68 * groove_intent.target_dna.low_end_anchor + 0.32 * kick_target
    )
    groove_intent.target_dna.syncopation = clamp(
        0.72 * groove_intent.target_dna.syncopation + 0.28 * kick_target
    )
    fresh = generate_pattern(
        bpm=source.bpm,
        bars=source.bars,
        meter=source.meter,
        intent=groove_intent,
        seed=source.metadata.master_seed,
        candidate=200 + candidate,
        name=source.name,
        style=source.metadata.style,
        performance_mode=(
            "rule" if source.metadata.performance_model == "rule-pocket-v1" else "auto"
        ),
        render_profile=source.metadata.render_profile,
    )
    protected = [
        event
        for event in source.events
        if event.instrument != InstrumentID.KICK
        or event.locked
        or event.origin == "user_edited"
        or event.grid_tick // source.meter.bar_ticks in source.bar_locks
    ]
    protected_kick_regions = {
        event.grid_tick // source.meter.bar_ticks
        for event in protected
        if event.instrument == InstrumentID.KICK
    }
    new_kicks = [
        event
        for event in fresh.events
        if event.instrument == InstrumentID.KICK
        and event.grid_tick // source.meter.bar_ticks not in protected_kick_regions
        and event.grid_tick // source.meter.bar_ticks not in source.bar_locks
    ]
    available_by_bar = {
        bar: [
            event
            for event in new_kicks
            if event.grid_tick // source.meter.bar_ticks == bar
        ]
        for bar in range(len(kick_targets))
    }
    selected_by_bar = {}

    def kick_rank(event):
        return (event.primary_role.value == "anchor", event.accent)

    for bar, target in enumerate(kick_targets):
        bar_kicks = available_by_bar[bar]
        wanted = max(1, round(len(bar_kicks) * (0.60 + 0.68 * target)))
        selected_by_bar[bar] = sorted(bar_kicks, key=kick_rank, reverse=True)[:wanted]

    # The raw generator may happen to create a busier recovery bar than peak bar.
    # Preserve locks first, then add available peak material before trimming only
    # the lowest-priority generated recovery hits.  This makes the shared
    # establish → develop → peak → recover contour observable, not aspirational.
    protected_kick_counts = {
        bar: sum(
            event.instrument == InstrumentID.KICK
            and event.grid_tick // source.meter.bar_ticks == bar
            for event in protected
        )
        for bar in range(len(kick_targets))
    }
    for phrase_start in range(0, len(kick_targets), 4):
        peak_bar, recovery_bar = phrase_start + 2, phrase_start + 3
        if recovery_bar >= len(kick_targets):
            continue
        peak_count = protected_kick_counts[peak_bar] + len(selected_by_bar[peak_bar])
        recovery_count = protected_kick_counts[recovery_bar] + len(
            selected_by_bar[recovery_bar]
        )
        selected_peak_ids = {event.event_id for event in selected_by_bar[peak_bar]}
        additions = [
            event
            for event in sorted(available_by_bar[peak_bar], key=kick_rank, reverse=True)
            if event.event_id not in selected_peak_ids
        ]
        needed = max(0, recovery_count - peak_count + 1)
        selected_by_bar[peak_bar].extend(additions[:needed])
        peak_count += min(needed, len(additions))
        excess = max(0, recovery_count - peak_count + 1)
        if excess:
            selected_by_bar[recovery_bar] = sorted(
                selected_by_bar[recovery_bar], key=kick_rank, reverse=True
            )[: max(0, len(selected_by_bar[recovery_bar]) - excess)]

    reduced_kicks = [
        event for bar in range(len(kick_targets)) for event in selected_by_bar[bar]
    ]
    result = deepcopy(source)
    result.events = sorted(
        protected + reduced_kicks,
        key=lambda event: (event.grid_tick, event.instrument.value, event.event_id),
    )
    result.pattern_id = f"{source.pattern_id}-co-{candidate}"
    result.analysis = None
    before, after = _kick_signature(source), _kick_signature(result)
    changed = len(before ^ after)
    total = max(1, len(before | after))
    changes = (
        []
        if not changed
        else [
            JointChange(
                target="kick_lane",
                operation="co_create",
                reason=f"jointly replanned {changed} Kick signature elements",
            )
        ]
    )
    return result, changes, 0.12 * changed / total


def _co_create(
    request: JointGenerateRequest, preference: BassPreferenceSummary | None = None
) -> list[JointGenerationResult]:
    pool: list[JointGenerationResult] = []
    pool_size = max(8, request.candidate_count * 2)
    kick_targets = _phrase_complexity_targets(
        request.groove_pattern.bars,
        request.shared_complexity_budget * (1 - request.bass_complexity_share),
    )
    bass_targets = _phrase_complexity_targets(
        request.groove_pattern.bars,
        request.shared_complexity_budget * request.bass_complexity_share,
    )
    for candidate in range(pool_size):
        groove, changes, cost = _co_created_groove(
            request.groove_pattern, candidate, kick_targets
        )
        aligned = _aligned_request(request, groove)
        bass = _apply_phrase_complexity_to_bass(
            generate_preference_search_bass_pattern(
                aligned,
                candidate=candidate,
                preference=preference,
            ),
            bass_targets,
        )
        pool.append(_make_result(request, groove, bass, changes, cost, preference))
    pool.sort(key=lambda item: item.joint_fitness, reverse=True)
    return pool[: request.candidate_count]


def generate_joint_candidates(
    request: JointGenerateRequest, preference: BassPreferenceSummary | None = None
) -> JointGenerateResponse:
    if request.mode == IntegrationMode.FOLLOW:
        candidates = _follow(request, preference)
    elif request.mode == IntegrationMode.NEGOTIATE:
        candidates = _negotiate(request, preference)
    else:
        candidates = _co_create(request, preference)
    if request.reference_render_analysis:
        for candidate in candidates:
            rendered = analyze_reference_render(
                candidate.groove_pattern, candidate.bass_pattern
            )
            candidate.rendered_audio = rendered
            if rendered is not None:
                candidate.joint_fitness = (
                    0.92 * candidate.joint_fitness + 0.08 * rendered.render_quality
                )
        candidates.sort(key=lambda item: item.joint_fitness, reverse=True)
    return JointGenerateResponse(mode=request.mode, candidates=candidates)
