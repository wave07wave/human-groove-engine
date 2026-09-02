from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.models.pattern import GroovePattern

from .analysis import analyze_bass_pattern
from .explain import attach_decision_traces, decision_trace
from .generation import generate_bass_candidates
from .harmony import harmony_at, role_for_pitch
from .integration import groove_context_from_pattern
from .midi import export_bass_midi
from .models import (
    BassDecisionTrace,
    BassGenerateRequest,
    BassGenerateResponse,
    BassGenerationRecord,
    BassIntent,
    BassIntentExchange,
    BassMutateRequest,
    BassPattern,
    BassPatternExchange,
    BassPreferenceRecord,
    BassPreferenceRequest,
    BassPreferenceSummary,
    BassPresetExchange,
    BassRefineRequest,
    GrooveContext,
    HarmonicRole,
    SaveBassPresetRequest,
)
from .mutation import mutate_bass_pattern, refine_bass_pattern
from .persistence import BassDatabase
from .preference import PREFERENCE_FEATURES
from .presets import BASS_PRESETS

router = APIRouter(prefix="/api/v1/bass", tags=["bass"])
db = BassDatabase()


@router.post("/context/from-groove", response_model=GrooveContext)
def context_from_groove(pattern: GroovePattern) -> GrooveContext:
    return groove_context_from_pattern(pattern)


@router.post("/generate", response_model=BassGenerateResponse)
def generate(request: BassGenerateRequest) -> BassGenerateResponse:
    profile = db.preference_summary(request.preset)
    candidates = generate_bass_candidates(request, profile)
    for pattern in candidates:
        db.save_generation(pattern)
    return BassGenerateResponse(candidates=candidates, preference_profile=profile)


@router.post("/evaluate", response_model=BassPattern)
def evaluate(pattern: BassPattern) -> BassPattern:
    pitch_roles = {
        HarmonicRole.ROOT,
        HarmonicRole.THIRD,
        HarmonicRole.FIFTH,
        HarmonicRole.SEVENTH,
        HarmonicRole.EXTENSION,
        HarmonicRole.SCALE_TONE,
        HarmonicRole.PASSING,
    }
    for event in pattern.events:
        if event.provenance.origin == "user_edited" and event.harmonic_role in pitch_roles:
            event.harmonic_role = role_for_pitch(
                event.pitch, harmony_at(pattern.harmony, event.grid_tick)
            )
    attach_decision_traces(pattern)
    pattern.analysis = analyze_bass_pattern(pattern)
    return pattern


@router.post("/explain/{event_id}", response_model=BassDecisionTrace)
def explain_event(event_id: str, pattern: BassPattern) -> BassDecisionTrace:
    event = next((item for item in pattern.events if item.event_id == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail="Bass event not found")
    return decision_trace(pattern, event)


@router.post("/mutate", response_model=BassPattern)
def mutate(request: BassMutateRequest) -> BassPattern:
    pattern = mutate_bass_pattern(
        request.pattern, request.bars, request.operation, request.preserve
    )
    db.save_generation(pattern)
    return pattern


@router.post("/refine", response_model=BassPattern)
def refine(request: BassRefineRequest) -> BassPattern:
    pattern = refine_bass_pattern(request.pattern, request.strength)
    db.save_generation(pattern)
    return pattern


@router.post("/export-midi")
def midi(pattern: BassPattern, channel: int = Query(0, ge=0, le=15)) -> Response:
    return Response(
        export_bass_midi(pattern, channel=channel),
        media_type="audio/midi",
        headers={"Content-Disposition": f'attachment; filename="{pattern.pattern_id}.mid"'},
    )


@router.get("/patterns", response_model=list[BassPattern])
def patterns() -> list[BassPattern]:
    return db.saved_patterns()


@router.post("/patterns", response_model=BassPattern)
def save_pattern(pattern: BassPattern) -> BassPattern:
    db.save_pattern(pattern)
    return pattern


@router.delete("/patterns/{pattern_id}", status_code=204)
def delete_pattern(pattern_id: str) -> Response:
    if not db.delete_pattern(pattern_id):
        raise HTTPException(status_code=404, detail="Saved bass pattern not found")
    return Response(status_code=204)


@router.get("/history/generations", response_model=list[BassGenerationRecord])
def generation_history(limit: int = Query(50, ge=1, le=200)) -> list[BassGenerationRecord]:
    return db.generation_history(limit)


@router.get("/history/generation-records/{generation_id}", response_model=BassPattern)
def generation_record_pattern(generation_id: int) -> BassPattern:
    pattern = db.generation_record_pattern(generation_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Bass generation record not found")
    return pattern


@router.get("/history/generations/{pattern_id}", response_model=BassPattern)
def generation_pattern(pattern_id: str) -> BassPattern:
    pattern = db.generation_pattern(pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Bass generation not found")
    return pattern


@router.get("/history/preferences", response_model=list[BassPreferenceRecord])
def preference_history(limit: int = Query(50, ge=1, le=200)) -> list[BassPreferenceRecord]:
    return db.preference_history(limit)


@router.post("/exchange/pattern/export", response_model=BassPatternExchange)
def export_pattern(pattern: BassPattern) -> BassPatternExchange:
    return BassPatternExchange(pattern=pattern)


@router.post("/exchange/pattern/import", response_model=BassPattern)
def import_pattern(exchange: BassPatternExchange) -> BassPattern:
    db.save_pattern(exchange.pattern)
    return exchange.pattern


@router.post("/exchange/intent/export", response_model=BassIntentExchange)
def export_intent(intent: BassIntent) -> BassIntentExchange:
    return BassIntentExchange(intent=intent)


@router.post("/exchange/intent/import", response_model=BassIntent)
def import_intent(exchange: BassIntentExchange) -> BassIntent:
    return exchange.intent


@router.post("/exchange/preset/export", response_model=BassPresetExchange)
def export_preset(request: BassPresetExchange) -> BassPresetExchange:
    return request


@router.post("/exchange/preset/import", response_model=BassPresetExchange)
def import_preset(exchange: BassPresetExchange) -> BassPresetExchange:
    db.save_preset(exchange.name, exchange.intent)
    return exchange


@router.post("/preferences", response_model=BassPreferenceSummary)
def save_preference(request: BassPreferenceRequest) -> BassPreferenceSummary:
    try:
        db.save_preference(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return db.preference_summary(request.candidate_a.metadata.preset)


@router.get("/preferences", response_model=BassPreferenceSummary)
def preferences(
    preset: str | None = Query(None, min_length=1, max_length=80),
) -> BassPreferenceSummary:
    return db.preference_summary(preset)


@router.get("/presets")
def presets() -> dict:
    return {
        "built_in": {name: intent.model_dump() for name, intent in BASS_PRESETS.items()},
        "user": {name: intent.model_dump() for name, intent in db.user_presets().items()},
    }


@router.post("/presets")
def save_preset(request: SaveBassPresetRequest) -> dict:
    db.save_preset(request.name, request.intent)
    return {"saved": request.name}


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "walking": True,
        "groove_context": True,
        "articulation_metadata": True,
        "long_form_bars": 64,
        "partial_regeneration": True,
        "preserve_options": [
            "rhythm",
            "pitch",
            "duration",
            "timing",
            "motif",
            "kick_relation",
            "register_shape",
        ],
        "intent_locks": ["rhythm_feel", "register", "kick_relationship"],
        "refine": True,
        "preference_learning": True,
        "preference_ranges": True,
        "preference_dimensions": len(PREFERENCE_FEATURES),
        "preference_scopes": True,
        "preference_ties": True,
        "preference_idempotency": True,
        "preference_effective_evidence": True,
        "joint_optimizer": True,
        "integration_modes": ["follow", "negotiate", "co_create"],
        "shared_complexity_budget": True,
        "midi_export": True,
        "midi_channel_configurable": True,
        "motown_bass_styles": ["standard", "jamerson"],
        "jamerson_inspired_generation": True,
        "pattern_library": True,
        "versioned_json_exchange": True,
        "history_api": True,
        "history_pattern_load": True,
        "audio_analysis": False,
        "mpe": False,
        "pcenter_audio_analysis": False,
    }
