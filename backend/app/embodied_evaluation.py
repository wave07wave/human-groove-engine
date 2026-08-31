from __future__ import annotations

import statistics

from app.models.evaluation import (
    EmbodiedEvaluationRequest,
    EmbodiedEvaluationResult,
    MotorTempoCalibrationRequest,
    MotorTempoProfile,
)
from app.persistence.database import GrooveDatabase


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def calibrate_motor_tempo(
    request: MotorTempoCalibrationRequest, db: GrooveDatabase
) -> MotorTempoProfile:
    intervals = [
        right - left for left, right in zip(request.timestamps_ms, request.timestamps_ms[1:])
    ]
    # The first three intervals are an explicit warm-up period.
    intervals = intervals[3:]
    median = statistics.median(intervals)
    deviations = [abs(value - median) for value in intervals]
    mad = statistics.median(deviations)
    accepted = [value for value in intervals if abs(value - median) <= max(80, 3 * mad)]
    interval = statistics.median(accepted)
    bpm = 60_000 / interval
    if not 30 <= bpm <= 300:
        raise ValueError("comfortable tap tempo must be between 30 and 300 BPM")
    dispersion = _clamp(
        statistics.median(abs(value - interval) for value in accepted) / max(1, interval)
    )
    confidence = _clamp(min(1, len(accepted) / 12) * (1 - 3.5 * dispersion))
    aliases = sorted({round(alias, 2) for alias in (bpm / 2, bpm, bpm * 2) if 30 <= alias <= 300})
    profile = MotorTempoProfile(
        bpm=round(bpm, 2),
        interval_ms=round(interval, 2),
        dispersion=round(dispersion, 4),
        confidence=round(confidence, 4),
        tempo_aliases=aliases,
        accepted_taps=len(accepted),
    )
    db.save_motor_tempo_profile(request.anonymous_session_id, profile)
    return profile


def save_embodied_evaluation(
    request: EmbodiedEvaluationRequest, db: GrooveDatabase
) -> EmbodiedEvaluationResult:
    db.save_embodied_evaluation(request)
    evidence = (
        "motion"
        if request.motion_observation is not None
        else "tap"
        if request.tap_observation is not None
        else "self_report"
    )
    return EmbodiedEvaluationResult(evidence_class=evidence)
