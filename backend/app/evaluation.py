from __future__ import annotations

import hashlib
import json
import math
import secrets
import statistics
import uuid
from datetime import UTC, datetime

from app.analysis.listener import analyze_pattern
from app.engine.generator import generate_pattern
from app.models.evaluation import (
    BlindCandidate,
    BlindResponseRequest,
    BlindResponseResult,
    BlindSession,
    BlindSessionRequest,
    EvaluationGroupSummary,
    EvaluationSummary,
)
from app.persistence.database import GrooveDatabase

DECLARED_GROUPS = ("producer", "drummer", "general")
ALL_GROUPS = (*DECLARED_GROUPS, "undisclosed")
MINIMUM_PER_GROUP = 20


def create_blind_session(request: BlindSessionRequest, db: GrooveDatabase) -> BlindSession:
    generation = request.generation
    session_id = uuid.uuid4().hex
    variants = {}
    for variant, performance_mode in (("learned", "auto"), ("rule", "rule")):
        pattern = generate_pattern(
            bpm=generation.bpm,
            bars=generation.bars,
            meter=generation.meter,
            intent=generation.intent,
            seed=generation.seed,
            candidate=0,
            name="Blind listening candidate",
            style=generation.preset,
            performance_mode=performance_mode,
            render_profile=generation.render_profile,
        )
        pattern.analysis = analyze_pattern(pattern, include_render=False)
        variants[variant] = pattern

    learned_model = variants["learned"].metadata.performance_model
    rule_model = variants["rule"].metadata.performance_model
    if learned_model == rule_model:
        raise RuntimeError("learned performance model is unavailable for blind comparison")

    order = ["learned", "rule"]
    if secrets.randbelow(2):
        order.reverse()
    started_at = datetime.now(UTC)
    fingerprint_payload = generation.model_dump(mode="json")
    fingerprint_payload.pop("performance_mode", None)
    fingerprint_payload.pop("candidate_count", None)
    stimulus_key = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    configuration_payload = dict(fingerprint_payload)
    configuration_payload.pop("seed", None)
    study_config_key = hashlib.sha256(
        json.dumps(configuration_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    left, right = variants[order[0]], variants[order[1]]
    left.pattern_id = f"{session_id}-left"
    right.pattern_id = f"{session_id}-right"
    db.create_blind_evaluation(
        session_id=session_id,
        participant_group=request.participant_group,
        left_variant=order[0],
        right_variant=order[1],
        left_pattern=left,
        right_pattern=right,
        started_at=started_at,
        study_run_id=request.study_run_id,
        trial_index=request.trial_index,
        stimulus_key=stimulus_key,
        study_config_key=study_config_key,
    )
    public_left = left.model_copy(deep=True)
    public_right = right.model_copy(deep=True)
    for pattern in (public_left, public_right):
        pattern.metadata.performance_model = "blind"
        pattern.metadata.performance_model_version = "hidden-until-response"
        pattern.analysis = None
    return BlindSession(
        session_id=session_id,
        participant_group=request.participant_group,
        started_at=started_at,
        study_run_id=request.study_run_id,
        trial_index=request.trial_index,
        candidates=[
            BlindCandidate(position="left", pattern=public_left),
            BlindCandidate(position="right", pattern=public_right),
        ],
    )


def answer_blind_session(
    request: BlindResponseRequest, db: GrooveDatabase
) -> BlindResponseResult:
    row = db.answer_blind_evaluation(
        session_id=request.session_id,
        selected=request.selected,
        decision_time_ms=request.decision_time_ms,
        saved_choice=request.saved_choice,
    )
    selected_variant = (
        "tie" if request.selected == "tie" else row[f"{request.selected}_variant"]
    )
    return BlindResponseResult(
        selected_variant=selected_variant,
        left_variant=row["left_variant"],
        right_variant=row["right_variant"],
    )


def _wilson_interval(wins: int, total: int) -> tuple[float, float]:
    if total == 0:
        return 0.0, 1.0
    z = 1.96
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def evaluation_summary(db: GrooveDatabase) -> EvaluationSummary:
    rows = db.completed_blind_evaluations()
    summaries = []
    for group in ALL_GROUPS:
        group_rows = [row for row in rows if row["participant_group"] == group]
        learned_wins = sum(
            row["selected"] != "tie"
            and row[f'{row["selected"]}_variant'] == "learned"
            for row in group_rows
        )
        rule_wins = sum(
            row["selected"] != "tie" and row[f'{row["selected"]}_variant'] == "rule"
            for row in group_rows
        )
        ties = sum(row["selected"] == "tie" for row in group_rows)
        decisive = learned_wins + rule_wins
        low, high = _wilson_interval(learned_wins, decisive)
        times = [int(row["decision_time_ms"]) for row in group_rows]
        saved = sum(row["saved_choice"] != "none" for row in group_rows)
        trials_by_run: dict[str, set[int]] = {}
        for row in group_rows:
            if row["study_run_id"] and row["trial_index"] is not None:
                trials_by_run.setdefault(row["study_run_id"], set()).add(row["trial_index"])
        completed_blocks = sum(indices == set(range(6)) for indices in trials_by_run.values())
        summaries.append(
            EvaluationGroupSummary(
                participant_group=group,
                comparisons=len(group_rows),
                completed_blocks=completed_blocks,
                learned_wins=learned_wins,
                rule_wins=rule_wins,
                ties=ties,
                learned_win_rate=learned_wins / decisive if decisive else 0.5,
                confidence_low=low,
                confidence_high=high,
                median_decision_ms=round(statistics.median(times)) if times else None,
                saved_rate=saved / len(group_rows) if group_rows else 0,
            )
        )

    declared = [item for item in summaries if item.participant_group in DECLARED_GROUPS]
    repeated: dict[tuple[str, str], list] = {}
    for row in rows:
        if row["study_run_id"] and row["stimulus_key"]:
            repeated.setdefault((row["study_run_id"], row["stimulus_key"]), []).append(row)
    repeat_pairs = [values for values in repeated.values() if len(values) >= 2]

    def selected_variant(row) -> str:
        if row["selected"] == "tie":
            return "tie"
        return row[f'{row["selected"]}_variant']

    consistent = sum(
        selected_variant(values[0]) == selected_variant(values[-1]) for values in repeat_pairs
    )
    enough = all(item.completed_blocks >= MINIMUM_PER_GROUP for item in declared)
    if not enough:
        verdict = "collecting"
    elif all(item.confidence_low > 0.5 for item in declared):
        verdict = "learned_supported"
    elif all(item.confidence_high < 0.5 for item in declared):
        verdict = "rule_supported"
    else:
        verdict = "inconclusive"
    return EvaluationSummary(
        completed=len(rows),
        groups=summaries,
        verdict=verdict,
        perceptual_claim_allowed=verdict == "learned_supported",
        eligible_repeat_pairs=len(repeat_pairs),
        repeat_consistency=consistent / len(repeat_pairs) if repeat_pairs else None,
        caveat=(
            "This is an application-level randomized comparison, not a universal measure of "
            "musical quality. Report participant groups and confidence intervals separately."
        ),
    )
