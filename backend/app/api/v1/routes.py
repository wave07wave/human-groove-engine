from fastapi import APIRouter, Response

from app.analysis.listener import analyze_pattern
from app.engine.mutation import regenerate_selected
from app.engine.optimizer import generate_candidates
from app.midi.exporter import export_midi
from app.models.api import (
    GenerateRequest,
    GenerateResponse,
    MutateRequest,
    PreferenceRequest,
    PresetsResponse,
    SavePresetRequest,
)
from app.models.pattern import GroovePattern
from app.persistence.database import GrooveDatabase
from app.presets import PRESETS

router = APIRouter(prefix="/api/v1")
db = GrooveDatabase()


@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    candidates = generate_candidates(
        bpm=request.bpm,
        bars=request.bars,
        meter=request.meter,
        intent=request.intent,
        seed=request.seed,
        count=request.candidate_count,
        mode=request.mode,
        preset=request.preset,
    )
    for pattern in candidates:
        db.save_generation(pattern)
    return GenerateResponse(candidates=candidates)


@router.post("/evaluate", response_model=GroovePattern)
def evaluate(pattern: GroovePattern) -> GroovePattern:
    pattern.analysis = analyze_pattern(pattern)
    return pattern


@router.post("/mutate", response_model=GroovePattern)
def mutate(request: MutateRequest) -> GroovePattern:
    pattern = regenerate_selected(
        request.pattern, request.instruments, request.bars, request.operation
    )
    pattern.analysis = analyze_pattern(pattern)
    db.save_generation(pattern)
    return pattern


@router.post("/export-midi")
def midi(pattern: GroovePattern) -> Response:
    return Response(
        export_midi(pattern),
        media_type="audio/midi",
        headers={"Content-Disposition": f'attachment; filename="{pattern.pattern_id}.mid"'},
    )


@router.post("/preferences")
def save_preference(request: PreferenceRequest) -> dict:
    db.save_preference(request)
    return db.preference_summary()


@router.get("/preferences")
def preferences() -> dict:
    return db.preference_summary()


@router.get("/presets", response_model=PresetsResponse)
def presets() -> PresetsResponse:
    built_in = {name: intent.model_dump() for name, intent in PRESETS.items()}
    user = {name: intent.model_dump() for name, intent in db.user_presets().items()}
    return PresetsResponse(built_in=built_in, user=user)


@router.post("/presets")
def save_preset(request: SavePresetRequest) -> dict:
    db.save_preset(request.name, request.intent)
    return {"saved": request.name}


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "polyrhythm": False,
        "audio_analysis": False,
        "groove_transfer": False,
        "realtime_midi": False,
        "partial_regeneration": True,
        "long_form_bars": 64,
        "midi_export": True,
        "preference_learning": True,
    }
