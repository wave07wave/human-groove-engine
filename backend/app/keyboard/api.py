from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Response

from .generation import (
    analyze_keyboard_pattern,
    generate_keyboard_candidates,
    regenerate_keyboard_pattern,
)
from .midi import export_keyboard_midi
from .models import (
    KEYBOARD_ANALYSIS_VERSION,
    KEYBOARD_GENERATION_VERSION,
    KeyboardGenerateRequest,
    KeyboardGenerateResponse,
    KeyboardGenerationRecord,
    KeyboardMutateRequest,
    KeyboardPattern,
    KeyboardPatternExchange,
)
from .persistence import KeyboardDatabase

router = APIRouter(prefix="/api/v1/keyboard", tags=["keyboard"])
db = KeyboardDatabase()


def _midi_content_disposition(pattern_id: str) -> str:
    """Build an ASCII-safe header while retaining a UTF-8 download name."""
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", pattern_id).strip(".-")
    ascii_stem = (ascii_stem or "keyboard-pattern")[:120]
    encoded_name = quote(f"{pattern_id[:120]}.mid", safe="")
    return (
        f'attachment; filename="{ascii_stem}.mid"; '
        f"filename*=UTF-8''{encoded_name}"
    )


@router.post("/generate", response_model=KeyboardGenerateResponse)
def generate(request: KeyboardGenerateRequest) -> KeyboardGenerateResponse:
    try:
        candidates = generate_keyboard_candidates(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    db.save_generations(candidates)
    return KeyboardGenerateResponse(candidates=candidates)


@router.post("/evaluate", response_model=KeyboardPattern)
def evaluate(pattern: KeyboardPattern) -> KeyboardPattern:
    try:
        pattern.analysis = analyze_keyboard_pattern(pattern)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    pattern.metadata.keyboard_analysis_version = KEYBOARD_ANALYSIS_VERSION
    return pattern


@router.post("/mutate", response_model=KeyboardPattern)
def mutate(request: KeyboardMutateRequest) -> KeyboardPattern:
    try:
        pattern = regenerate_keyboard_pattern(request.pattern, request.bars)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if pattern.pattern_id != request.pattern.pattern_id:
        db.save_generation(pattern)
    return pattern


@router.post("/export-midi")
def midi(pattern: KeyboardPattern) -> Response:
    return Response(
        export_keyboard_midi(pattern),
        media_type="audio/midi",
        headers={"Content-Disposition": _midi_content_disposition(pattern.pattern_id)},
    )


@router.get("/patterns", response_model=list[KeyboardPattern])
def patterns() -> list[KeyboardPattern]:
    return db.saved_patterns()


@router.post("/patterns", response_model=KeyboardPattern)
def save_pattern(pattern: KeyboardPattern) -> KeyboardPattern:
    db.save_pattern(pattern)
    return pattern


@router.delete("/patterns/{pattern_id}", status_code=204)
def delete_pattern(pattern_id: str) -> Response:
    if not db.delete_pattern(pattern_id):
        raise HTTPException(status_code=404, detail="Saved keyboard pattern not found")
    return Response(status_code=204)


@router.get("/history/generations", response_model=list[KeyboardGenerationRecord])
def generation_history(limit: int = Query(50, ge=1, le=200)) -> list[KeyboardGenerationRecord]:
    return db.generation_history(limit)


@router.get(
    "/history/generation-records/{generation_id}", response_model=KeyboardPattern
)
def generation_record_pattern(generation_id: int) -> KeyboardPattern:
    pattern = db.generation_record_pattern(generation_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Keyboard generation record not found")
    return pattern


@router.post("/exchange/pattern/export", response_model=KeyboardPatternExchange)
def export_pattern(pattern: KeyboardPattern) -> KeyboardPatternExchange:
    return KeyboardPatternExchange(pattern=pattern)


@router.post("/exchange/pattern/import", response_model=KeyboardPattern)
def import_pattern(exchange: KeyboardPatternExchange) -> KeyboardPattern:
    db.save_pattern(exchange.pattern)
    return exchange.pattern


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "styles": ["standard", "earl", "joe", "johnny", "blend"],
        "blend_controls": ["earl", "joe", "johnny"],
        "deterministic_generation": True,
        "bpm_compensation": True,
        "rhythm_context": ["kick", "snare", "bass"],
        "instruments": [
            "acoustic_piano",
            "tonewheel_organ",
            "electric_piano",
            "celeste",
        ],
        "partial_regeneration": True,
        "pattern_library": True,
        "history_api": True,
        "midi_export": True,
        "external_samples": False,
        "source_phrases": False,
        "generation_version": KEYBOARD_GENERATION_VERSION,
        "analysis_version": KEYBOARD_ANALYSIS_VERSION,
    }
