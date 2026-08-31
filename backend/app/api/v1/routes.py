from fastapi import APIRouter, HTTPException, Query, Response

from app.analysis.listener import analyze_pattern
from app.audio import available_render_profiles
from app.embodied_evaluation import calibrate_motor_tempo, save_embodied_evaluation
from app.engine.mutation import regenerate_selected
from app.engine.optimizer import generate_candidates
from app.engine.performance import model_status
from app.evaluation import answer_blind_session, create_blind_session, evaluation_summary
from app.midi.exporter import export_midi
from app.models.api import (
    GenerateRequest,
    GenerateResponse,
    MutateRequest,
    PreferenceRequest,
    PresetsResponse,
    SavePresetRequest,
)
from app.models.evaluation import (
    BlindResponseRequest,
    BlindResponseResult,
    BlindSession,
    BlindSessionRequest,
    EmbodiedEvaluationRequest,
    EmbodiedEvaluationResult,
    EmbodiedEvaluationSummary,
    EvaluationSummary,
    MotorTempoCalibrationRequest,
    MotorTempoProfile,
)
from app.models.pattern import GroovePattern
from app.models.preference import GroovePreferenceSummary
from app.models.quality import QualityAuditReport
from app.models.reference import (
    IntentTransformRequest,
    IntentTransformResponse,
    MidiReferenceAnalysis,
    MidiReferenceRequest,
    TapAnalysis,
    TapAnalyzeRequest,
)
from app.persistence.database import GrooveDatabase
from app.presets import PRESETS
from app.quality import load_quality_audit
from app.reference import analyze_midi_reference, analyze_taps, transform_intent

router = APIRouter(prefix="/api/v1")
db = GrooveDatabase()


@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    preference = db.preference_summary(request.preset)
    candidates = generate_candidates(
        bpm=request.bpm,
        bars=request.bars,
        meter=request.meter,
        intent=request.intent,
        seed=request.seed,
        count=request.candidate_count,
        mode=request.mode,
        performance_mode=request.performance_mode,
        render_profile=request.render_profile,
        preset=request.preset,
        candidate_strategy=request.candidate_strategy,
        preference=preference,
        motor_tempo_profile=db.motor_tempo_profile(request.anonymous_session_id),
        embodied_operator_scores=db.embodied_operator_scores(
            request.anonymous_session_id,
            request.preset,
            f"{request.meter.numerator}/{request.meter.denominator}",
        ),
    )
    for pattern in candidates:
        db.save_generation(pattern)
    return GenerateResponse(candidates=candidates, preference_profile=preference)


@router.post("/evaluate", response_model=GroovePattern)
def evaluate(pattern: GroovePattern) -> GroovePattern:
    pattern.analysis = analyze_pattern(pattern, include_render=True)
    return pattern


@router.post("/mutate", response_model=GroovePattern)
def mutate(request: MutateRequest) -> GroovePattern:
    pattern = regenerate_selected(
        request.pattern, request.instruments, request.bars, request.operation
    )
    pattern.analysis = analyze_pattern(pattern, include_render=True)
    db.save_generation(pattern)
    return pattern


@router.post("/export-midi")
def midi(pattern: GroovePattern) -> Response:
    return Response(
        export_midi(pattern),
        media_type="audio/midi",
        headers={"Content-Disposition": f'attachment; filename="{pattern.pattern_id}.mid"'},
    )


@router.post("/preferences", response_model=GroovePreferenceSummary)
def save_preference(request: PreferenceRequest) -> GroovePreferenceSummary:
    try:
        db.save_preference(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return db.preference_summary(request.candidate_a.metadata.style)


@router.get("/preferences", response_model=GroovePreferenceSummary)
def preferences(
    style: str | None = Query(None, min_length=1, max_length=80),
) -> GroovePreferenceSummary:
    return db.preference_summary(style)


@router.post("/evaluation/sessions", response_model=BlindSession)
def start_blind_evaluation(request: BlindSessionRequest) -> BlindSession:
    try:
        return create_blind_session(request, db)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/evaluation/responses", response_model=BlindResponseResult)
def submit_blind_evaluation(request: BlindResponseRequest) -> BlindResponseResult:
    try:
        return answer_blind_session(request, db)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="listening session not found") from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/evaluation/summary", response_model=EvaluationSummary)
def blind_evaluation_summary() -> EvaluationSummary:
    return evaluation_summary(db)


@router.post("/evaluation/embodied", response_model=EmbodiedEvaluationResult)
def submit_embodied_evaluation(request: EmbodiedEvaluationRequest) -> EmbodiedEvaluationResult:
    return save_embodied_evaluation(request, db)


@router.get("/evaluation/embodied/summary", response_model=EmbodiedEvaluationSummary)
def embodied_evaluation_summary(
    anonymous_session_id: str = Query(..., min_length=8, max_length=80, pattern=r"^[A-Za-z0-9-]+$"),
) -> EmbodiedEvaluationSummary:
    return db.embodied_evaluation_summary(anonymous_session_id)


@router.post("/evaluation/motor-tempo", response_model=MotorTempoProfile)
def motor_tempo_calibration(request: MotorTempoCalibrationRequest) -> MotorTempoProfile:
    try:
        return calibrate_motor_tempo(request, db)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/quality/audit", response_model=QualityAuditReport)
def quality_audit() -> QualityAuditReport:
    try:
        return load_quality_audit()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/presets", response_model=PresetsResponse)
def presets() -> PresetsResponse:
    built_in = {name: intent.model_dump() for name, intent in PRESETS.items()}
    user = {name: intent.model_dump() for name, intent in db.user_presets().items()}
    return PresetsResponse(built_in=built_in, user=user)


@router.post("/presets")
def save_preset(request: SavePresetRequest) -> dict:
    db.save_preset(request.name, request.intent)
    return {"saved": request.name}


@router.post("/reference/taps", response_model=TapAnalysis)
def tap_reference(request: TapAnalyzeRequest) -> TapAnalysis:
    try:
        return analyze_taps(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/reference/midi", response_model=MidiReferenceAnalysis)
def midi_reference(request: MidiReferenceRequest) -> MidiReferenceAnalysis:
    try:
        return analyze_midi_reference(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/intent/transform", response_model=IntentTransformResponse)
def language_transform(request: IntentTransformRequest) -> IntentTransformResponse:
    return transform_intent(request.text, request.current_intent)


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
        "preference_reranking": True,
        "preference_dimensions": 21,
        "preference_scopes": True,
        "preference_ties": True,
        "idempotent_preference_trials": True,
        "effective_preference_evidence": True,
        "style_conditioned_pocket": True,
        "genre_rhythm_language": True,
        "learned_performance_model": model_status(),
        "reference_render_analysis": True,
        "render_profiles": available_render_profiles(),
        "tap_to_groove": True,
        "midi_reference_analysis": True,
        "deterministic_language_transform": True,
        "phrase_energy_curve": True,
        "blind_listening_evaluation": True,
        "embodied_evaluation": True,
        "comfortable_tap_calibration": True,
        "embodied_features": True,
        "blind_listening_blocks": 6,
        "repeat_consistency": True,
        "technical_quality_audit": True,
        "grid_subdivisions_per_quarter": [2, 3, 4, 6, 8],
        "triplet_grid": True,
        "thirty_second_grid": True,
    }
