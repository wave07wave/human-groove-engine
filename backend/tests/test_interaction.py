from __future__ import annotations

from statistics import mean

import pytest
from fastapi.testclient import TestClient

from app.bass import interaction as interaction_module
from app.bass.interaction import (
    IntegrationMode,
    JointGenerateRequest,
    _phrase_complexity_targets,
    generate_joint_candidates,
)
from app.bass.models import BassGenerateRequest, BassPreferenceSummary, PreferenceRange
from app.engine.generator import generate_pattern
from app.main import app
from app.models.event import InstrumentID
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition


def source_pair() -> tuple:
    meter = MeterDefinition.from_name("4/4")
    groove = generate_pattern(bpm=104, bars=4, meter=meter, intent=GrooveIntent(), seed=902)
    bass = BassGenerateRequest(
        bpm=104,
        bars=4,
        meter=meter,
        harmony="Dm7 | G7 | Cmaj7 | A7",
        seed=902,
        candidate_count=2,
    )
    return groove, bass


def request_for(mode: IntegrationMode, count: int = 2) -> JointGenerateRequest:
    groove, bass = source_pair()
    return JointGenerateRequest(
        groove_pattern=groove,
        bass_request=bass,
        mode=mode,
        candidate_count=count,
    )


def strong_preference() -> BassPreferenceSummary:
    return BassPreferenceSummary(
        comparisons=20,
        decisive_comparisons=20,
        effective_comparisons=20,
        learning_confidence=1,
        personal_weight=0.8,
        feature_weights={"density": 1},
        preferred_ranges={
            "density": PreferenceRange(
                mean=0.7,
                low=0.6,
                high=0.8,
                uncertainty=0,
                observations=20,
                evidence=1,
            )
        },
    )


def test_co_create_passes_preference_to_every_bass_search_candidate(monkeypatch) -> None:
    calls: list[tuple[int, BassPreferenceSummary | None]] = []
    original = interaction_module.generate_preference_search_bass_pattern

    def tracked(request, *, candidate, preference):
        calls.append((candidate, preference))
        return original(request, candidate=candidate, preference=preference)

    monkeypatch.setattr(
        interaction_module,
        "generate_preference_search_bass_pattern",
        tracked,
    )
    preference = strong_preference()
    generate_joint_candidates(request_for(IntegrationMode.CO_CREATE, count=1), preference)

    assert [candidate for candidate, _ in calls] == list(range(8))
    assert all(received is preference for _, received in calls)


def test_follow_keeps_groove_events_exactly_fixed() -> None:
    request = request_for(IntegrationMode.FOLLOW)
    response = generate_joint_candidates(request)
    source = [event.model_dump() for event in request.groove_pattern.events]
    assert len(response.candidates) == 2
    assert all(
        [event.model_dump() for event in candidate.groove_pattern.events] == source
        for candidate in response.candidates
    )
    assert all(not candidate.changes for candidate in response.candidates)
    assert all(
        candidate.groove_pattern.model_dump_json() == request.groove_pattern.model_dump_json()
        for candidate in response.candidates
    )


@pytest.mark.parametrize(
    ("meter_name", "bars"),
    [("4/4", 1), ("3/4", 4), ("5/8", 8), ("6/8", 16), ("12/8", 4), ("4/4", 64)],
)
def test_follow_contract_across_meter_and_length_boundaries(
    meter_name: str, bars: int
) -> None:
    meter = MeterDefinition.from_name(meter_name)
    groove = generate_pattern(
        bpm=118, bars=bars, meter=meter, intent=GrooveIntent(), seed=1301
    )
    request = JointGenerateRequest(
        groove_pattern=groove,
        bass_request=BassGenerateRequest(
            bpm=118,
            bars=bars,
            meter=meter,
            harmony="Dm7 | G7 | Cmaj7 | A7",
            seed=1301,
            candidate_count=1,
        ),
        mode=IntegrationMode.FOLLOW,
        candidate_count=1,
    )
    source = groove.model_dump_json()
    response = generate_joint_candidates(request)

    assert response.candidates[0].groove_pattern.model_dump_json() == source
    context = response.candidates[0].bass_pattern.groove_context
    assert context is not None
    assert context.meter == meter
    assert all(0 <= kick.performed_tick < bars * meter.bar_ticks for kick in context.kick_events)


def test_negotiate_changes_at_most_one_unlocked_kick() -> None:
    request = request_for(IntegrationMode.NEGOTIATE, count=4)
    first_kick = next(
        event for event in request.groove_pattern.events if event.instrument == InstrumentID.KICK
    )
    first_kick.locked = True
    original = first_kick.model_dump()
    user_kick = next(
        event
        for event in request.groove_pattern.events
        if event.instrument == InstrumentID.KICK and event.event_id != first_kick.event_id
    )
    user_kick.origin = "user_edited"
    user_original = user_kick.model_dump()
    response = generate_joint_candidates(request)
    assert response.candidates
    for candidate in response.candidates:
        assert len(candidate.changes) <= 1
        preserved = next(
            event
            for event in candidate.groove_pattern.events
            if event.event_id == first_kick.event_id
        )
        assert preserved.model_dump() == original
        preserved_user = next(
            event
            for event in candidate.groove_pattern.events
            if event.event_id == user_kick.event_id
        )
        assert preserved_user.model_dump() == user_original
        assert 0 <= candidate.change_cost < 0.1


def test_co_create_only_replans_unlocked_kick_lane() -> None:
    request = request_for(IntegrationMode.CO_CREATE)
    first_kick = next(
        event for event in request.groove_pattern.events if event.instrument == InstrumentID.KICK
    )
    first_kick.locked = True
    user_kick = next(
        event
        for event in request.groove_pattern.events
        if event.instrument == InstrumentID.KICK and event.event_id != first_kick.event_id
    )
    user_kick.origin = "user_edited"
    user_original = user_kick.model_dump()
    non_kick = [
        event.model_dump()
        for event in request.groove_pattern.events
        if event.instrument != InstrumentID.KICK
    ]
    response = generate_joint_candidates(request)
    assert len(response.candidates) == 2
    for candidate in response.candidates:
        assert [
            event.model_dump()
            for event in candidate.groove_pattern.events
            if event.instrument != InstrumentID.KICK
        ] == non_kick
        preserved = next(
            event
            for event in candidate.groove_pattern.events
            if event.event_id == first_kick.event_id
        )
        assert preserved.locked
        preserved_user = next(
            event
            for event in candidate.groove_pattern.events
            if event.event_id == user_kick.event_id
        )
        assert preserved_user.model_dump() == user_original
        assert 0 <= candidate.complexity_fit <= 1
        assert candidate.interaction.pulse_reinforcement >= 0


@pytest.mark.parametrize("mode", [IntegrationMode.NEGOTIATE, IntegrationMode.CO_CREATE])
def test_joint_modes_respect_kick_instrument_lock(mode: IntegrationMode) -> None:
    request = request_for(mode, count=2)
    request.groove_pattern.instrument_locks.add(InstrumentID.KICK)
    source = request.groove_pattern.model_dump_json()

    response = generate_joint_candidates(request)

    assert response.candidates
    assert all(item.groove_pattern.model_dump_json() == source for item in response.candidates)
    assert all(not item.changes and item.change_cost == 0 for item in response.candidates)


def test_joint_generation_is_deterministic() -> None:
    request = request_for(IntegrationMode.CO_CREATE, count=1)
    left = generate_joint_candidates(request)
    right = generate_joint_candidates(request)
    assert left.model_dump_json() == right.model_dump_json()


def test_shared_complexity_budget_changes_generated_low_end_activity() -> None:
    low = request_for(IntegrationMode.CO_CREATE, count=4)
    high = request_for(IntegrationMode.CO_CREATE, count=4)
    low.shared_complexity_budget = 0.1
    high.shared_complexity_budget = 0.9
    low.bass_complexity_share = high.bass_complexity_share = 0.7

    low_response = generate_joint_candidates(low)
    high_response = generate_joint_candidates(high)

    assert mean(len(item.bass_pattern.events) for item in high_response.candidates) > mean(
        len(item.bass_pattern.events) for item in low_response.candidates
    )
    assert mean(item.complexity_fit for item in high_response.candidates) > mean(
        item.complexity_fit for item in low_response.candidates
    )


def test_phrase_complexity_repeats_establish_develop_peak_recover_contour() -> None:
    targets = _phrase_complexity_targets(8, 0.8)

    assert targets[:4] == pytest.approx([0.576, 0.832, 0.944, 0.496])
    assert targets[4:] == pytest.approx(targets[:4])
    assert targets[2] > targets[1] > targets[0] > targets[3]


def test_co_create_applies_shared_phrase_peak_and_recovery() -> None:
    result = generate_joint_candidates(request_for(IntegrationMode.CO_CREATE, count=1))
    candidate = result.candidates[0]
    bar_ticks = candidate.groove_pattern.meter.bar_ticks
    kick_counts = [
        sum(
            event.instrument == InstrumentID.KICK
            and event.grid_tick // bar_ticks == bar
            for event in candidate.groove_pattern.events
        )
        for bar in range(4)
    ]
    bass_events = candidate.bass_pattern.events
    bass_counts = [
        sum(event.grid_tick // bar_ticks == bar for event in bass_events) for bar in range(4)
    ]

    assert kick_counts[2] > kick_counts[3]
    assert bass_counts[2] > bass_counts[3]
    assert any(
        event.rhythmic_role.value == "recovery"
        and event.grid_tick // bar_ticks == 3
        for event in bass_events
    )


def test_co_create_returns_distinct_joint_candidates() -> None:
    response = generate_joint_candidates(request_for(IntegrationMode.CO_CREATE, count=4))
    signatures = {
        (
            tuple(
                (event.grid_tick, event.pitch)
                for event in candidate.bass_pattern.events
            ),
            tuple(
                (event.grid_tick, event.velocity)
                for event in candidate.groove_pattern.events
                if event.instrument == InstrumentID.KICK
            ),
        )
        for candidate in response.candidates
    }

    assert len(response.candidates) == 4
    assert len(signatures) == 4


def test_joint_api_contract() -> None:
    request = request_for(IntegrationMode.NEGOTIATE, count=1)
    response = TestClient(app).post(
        "/api/v1/interaction/generate", json=request.model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "negotiate"
    assert len(payload["candidates"]) == 1


def test_joint_reference_render_uses_the_generated_bass_lane() -> None:
    request = request_for(IntegrationMode.FOLLOW, count=1)
    request.reference_render_analysis = True
    response = generate_joint_candidates(request)
    rendered = response.candidates[0].rendered_audio
    assert rendered is not None
    assert rendered.scope == "joint"
    assert rendered.low_end_collision_applicable
    assert rendered.rendered_events > 0


def test_joint_api_rejects_mismatched_structure() -> None:
    request = request_for(IntegrationMode.FOLLOW, count=1).model_dump(mode="json")
    request["bass_request"]["bars"] = request["groove_pattern"]["bars"] + 1
    response = TestClient(app).post("/api/v1/interaction/generate", json=request)
    assert response.status_code == 422
    assert "matching output lengths" in response.text
