from __future__ import annotations

import base64
import binascii
import math
from dataclasses import dataclass
from io import BytesIO

import mido
import numpy as np

from app.analysis.metrics import clamp, measure_dna
from app.config import DRUM_PITCHES, MAX_MICROTIMING_US, PPQ
from app.engine.pulse import metric_gravity
from app.models.event import EventRole, GrooveEvent, InstrumentID
from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition
from app.models.pattern import GroovePattern, PatternMetadata
from app.models.reference import (
    IntentChange,
    IntentTransformResponse,
    MidiReferenceAnalysis,
    MidiReferenceRequest,
    TapAnalysis,
    TapAnalyzeRequest,
)

MAX_MIDI_BYTES = 2_000_000
SUPPORTED_METERS = {"4/4", "3/4", "5/4", "5/8", "6/8", "12/8"}
PITCH_INSTRUMENT = {
    36: InstrumentID.KICK,
    37: InstrumentID.SNARE,
    38: InstrumentID.SNARE,
    40: InstrumentID.SNARE,
    22: InstrumentID.CLOSED_HAT,
    42: InstrumentID.CLOSED_HAT,
    44: InstrumentID.CLOSED_HAT,
    26: InstrumentID.OPEN_HAT,
    46: InstrumentID.OPEN_HAT,
}


def analyze_taps(request: TapAnalyzeRequest) -> TapAnalysis:
    intervals = np.diff(np.asarray(request.timestamps_ms, dtype=float))
    median = float(np.median(intervals))
    if not 200 <= median <= 2_000:
        raise ValueError("tap tempo must be between 30 and 300 BPM")
    accepted = intervals[np.abs(intervals - median) <= median * 0.55]
    if len(accepted) < 2:
        raise ValueError("tap pattern is too irregular to estimate a pulse")
    alternating = 0.0
    tempo_interval = float(np.median(accepted))
    variation = float(np.std(accepted) / max(1, np.mean(accepted)))
    if len(accepted) >= 4:
        even = float(np.median(accepted[::2]))
        odd = float(np.median(accepted[1::2]))
        alternating = clamp(abs(even - odd) / max(1, even + odd) * 4)
        if alternating > 0.1:
            tempo_interval = (even + odd) / 2
            residuals = np.concatenate((accepted[::2] - even, accepted[1::2] - odd))
            variation = float(np.std(residuals) / max(1, tempo_interval))
    bpm = max(30.0, min(300.0, 60_000 / tempo_interval))
    stability = clamp(1 - variation * 3.2)
    intent = request.current_intent.model_copy(deep=True)
    dna = intent.target_dna
    dna.pulse_stability = clamp(0.45 * dna.pulse_stability + 0.55 * stability)
    dna.microtiming = clamp(0.55 * dna.microtiming + 0.45 * (1 - stability))
    dna.swing = clamp(0.7 * dna.swing + 0.3 * alternating)
    intent.movement_target = "swing" if alternating > 0.35 else intent.movement_target
    confidence = clamp(min(1, len(accepted) / 8) * 0.55 + stability * 0.45)
    return TapAnalysis(
        bpm=bpm,
        timing_stability=stability,
        alternating_feel=alternating,
        confidence=confidence,
        accepted_taps=len(accepted) + 1,
        suggested_intent=intent,
    )


def _meter_from_midi(numerator: int, denominator: int) -> tuple[MeterDefinition, list[str]]:
    name = f"{numerator}/{denominator}"
    if name in SUPPORTED_METERS:
        return MeterDefinition.from_name(name), []
    return MeterDefinition.from_name("4/4"), [f"Unsupported {name} meter was interpreted as 4/4"]


def _role(instrument: InstrumentID, meter: MeterDefinition, tick: int) -> EventRole:
    gravity = metric_gravity(meter, tick % meter.bar_ticks)
    if instrument == InstrumentID.KICK and gravity >= 0.75:
        return EventRole.ANCHOR
    if instrument == InstrumentID.SNARE and gravity >= 0.7:
        return EventRole.ANCHOR
    if gravity < 0.45:
        return EventRole.VIOLATION
    return EventRole.CONFIRMATION


def analyze_midi_reference(request: MidiReferenceRequest) -> MidiReferenceAnalysis:
    try:
        payload = base64.b64decode(request.midi_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("MIDI data is not valid base64") from error
    if not payload or len(payload) > MAX_MIDI_BYTES:
        raise ValueError("MIDI reference must be between 1 byte and 2 MB")
    try:
        midi = mido.MidiFile(file=BytesIO(payload))
    except (EOFError, OSError, ValueError) as error:
        raise ValueError("MIDI reference could not be parsed") from error
    if midi.type == 2:
        raise ValueError("asynchronous Type 2 MIDI is not supported")
    tempo = mido.bpm2tempo(120)
    numerator, denominator = 4, 4
    for track in midi.tracks:
        for message in track:
            if message.type == "set_tempo":
                tempo = message.tempo
                break
        for message in track:
            if message.type == "time_signature":
                numerator, denominator = message.numerator, message.denominator
                break
    bpm = max(30.0, min(300.0, float(mido.tempo2bpm(tempo))))
    meter, warnings = _meter_from_midi(numerator, denominator)
    absolute = 0
    raw_hits: list[tuple[int, int, int]] = []
    for message in mido.merge_tracks(midi.tracks):
        absolute += message.time
        if message.type == "note_on" and message.velocity > 0:
            raw_hits.append((absolute, message.note, message.velocity))
            if len(raw_hits) > 20_000:
                raise ValueError("MIDI reference contains more than 20,000 note onsets")
    if not raw_hits:
        raise ValueError("MIDI reference contains no note onsets")
    canonical_end = max(hit[0] for hit in raw_hits) * PPQ / midi.ticks_per_beat
    bars = max(1, min(64, math.ceil((canonical_end + 1) / meter.bar_ticks)))
    deduplicated: dict[tuple[InstrumentID, int], GrooveEvent] = {}
    for source_tick, pitch, velocity in raw_hits:
        canonical = source_tick * PPQ / midi.ticks_per_beat
        grid_tick = round(canonical / meter.subdivision_tick) * meter.subdivision_tick
        if grid_tick >= bars * meter.bar_ticks:
            grid_tick = bars * meter.bar_ticks - meter.subdivision_tick
        instrument = PITCH_INSTRUMENT.get(pitch, InstrumentID.PERCUSSION)
        microseconds = round((canonical - grid_tick) / PPQ * 60_000_000 / bpm)
        microseconds = max(-MAX_MICROTIMING_US, min(MAX_MICROTIMING_US, microseconds))
        event = GrooveEvent(
            event_id=f"reference-{instrument.value}-{grid_tick}",
            instrument=instrument,
            grid_tick=max(0, grid_tick),
            micro_offset_us=microseconds,
            duration_tick=max(60, meter.subdivision_tick // 2),
            velocity=velocity,
            pitch=DRUM_PITCHES.get(instrument.value),
            primary_role=_role(instrument, meter, grid_tick),
            accent=velocity / 127,
            origin="user_edited",
        )
        key = (instrument, event.grid_tick)
        if key not in deduplicated or event.velocity > deduplicated[key].velocity:
            deduplicated[key] = event
    reference_pattern = GroovePattern(
        pattern_id="midi-reference-analysis",
        name=request.filename,
        bpm=bpm,
        bars=bars,
        meter=meter,
        events=sorted(deduplicated.values(), key=lambda event: (event.grid_tick, event.event_id)),
        intent=request.current_intent,
        metadata=PatternMetadata(master_seed=0, style="MIDI Reference", render_profile="off"),
    )
    measured = measure_dna(reference_pattern)
    suggested = request.current_intent.model_copy(deep=True)
    for dimension in type(measured).model_fields:
        before = getattr(suggested.target_dna, dimension)
        value = clamp(0.35 * before + 0.65 * getattr(measured, dimension))
        setattr(suggested.target_dna, dimension, value)
    confidence = clamp(0.35 + min(0.45, len(raw_hits) / 256) + (0.2 if not warnings else 0.08))
    if bars == 64 and canonical_end > 64 * meter.bar_ticks:
        warnings.append("Only the first 64 bars are represented in the suggested intent")
    return MidiReferenceAnalysis(
        filename=request.filename,
        bpm=bpm,
        meter=meter,
        bars=bars,
        hit_count=len(raw_hits),
        measured_dna=measured,
        suggested_intent=suggested,
        confidence=confidence,
        warnings=warnings,
    )


@dataclass(frozen=True)
class LanguageRule:
    terms: tuple[str, ...]
    deltas: dict[str, float]
    reason: str
    style: str | None = None
    movement: str | None = None


LANGUAGE_RULES = (
    LanguageRule(
        ("跳ねない", "スウィングなし", "straight"), {"swing": -1}, "straight feel"
    ),
    LanguageRule(
        ("もっと跳ね", "跳ねる", "swing", "bounce"),
        {"swing": 0.2, "motor_affordance": 0.1, "syncopation": 0.06},
        "stronger bounce",
        movement="bounce",
    ),
    LanguageRule(
        ("後ろへ", "後ろに", "溜める", "laid back", "behind"),
        {"microtiming": 0.14, "pulse_stability": -0.04},
        "laid-back pocket",
        style="Laid Back",
        movement="laid_back",
    ),
    LanguageRule(
        ("前のめり", "前へ", "forward", "push"),
        {"anticipation": 0.16, "microtiming": 0.06},
        "forward pocket",
        style="Forward",
        movement="forward",
    ),
    LanguageRule(
        ("シンプル", "simple", "less busy", "減らす"),
        {"density": -0.18, "syncopation": -0.1, "variation": -0.1},
        "reduced activity",
    ),
    LanguageRule(
        ("複雑", "complex", "busy"),
        {"density": 0.14, "syncopation": 0.12, "metric_ambiguity": 0.1},
        "greater rhythmic complexity",
    ),
    LanguageRule(
        ("人間的", "人間味", "human", "loose"),
        {"microtiming": 0.16, "velocity_contrast": 0.1, "variation": 0.06},
        "more performed variation",
        style="Loose",
    ),
    LanguageRule(
        ("タイト", "tight", "正確"),
        {"microtiming": -0.16, "pulse_stability": 0.12},
        "tighter timing",
        style="Mechanical",
    ),
    LanguageRule(
        ("ファンキー", "funky", "funk"),
        {"interlock": 0.16, "ghost_density": 0.14, "syncopation": 0.1},
        "funk interlock",
        style="Funk",
    ),
    LanguageRule(
        ("催眠", "hypnotic", "反復"),
        {"hypnotic": 0.18, "repetition": 0.12, "variation": -0.08},
        "hypnotic repetition",
        style="Hypnotic",
    ),
    LanguageRule(
        ("盛り上", "展開", "develop", "build"),
        {"phrase_development": 0.2, "variation": 0.08},
        "stronger phrase development",
    ),
    LanguageRule(
        ("意外", "surprise", "unexpected"),
        {"surprise": 0.16, "syncopation": 0.08, "recovery_strength": 0.08},
        "resolvable surprise",
    ),
)


def transform_intent(text: str, current: GrooveIntent) -> IntentTransformResponse:
    normalized = text.casefold().strip()
    intent = current.model_copy(deep=True)
    changes: list[IntentChange] = []
    suggested_style = None
    matched = 0
    for rule in LANGUAGE_RULES:
        if not any(term in normalized for term in rule.terms):
            continue
        matched += 1
        for dimension, delta in rule.deltas.items():
            before = getattr(intent.target_dna, dimension)
            after = 0.0 if delta <= -1 else clamp(before + delta)
            setattr(intent.target_dna, dimension, after)
            if before != after:
                changes.append(
                    IntentChange(
                        dimension=dimension,
                        before=before,
                        after=after,
                        reason=rule.reason,
                    )
                )
        if rule.style:
            suggested_style = rule.style
        if rule.movement and intent.movement_target != rule.movement:
            changes.append(
                IntentChange(
                    dimension="movement_target",
                    before=intent.movement_target,
                    after=rule.movement,
                    reason=rule.reason,
                )
            )
            intent.movement_target = rule.movement
    if not matched:
        return IntentTransformResponse(
            intent=intent,
            changes=[],
            confidence=0,
            message="Recognized no supported musical direction; intent was not changed.",
        )
    return IntentTransformResponse(
        intent=intent,
        suggested_style=suggested_style,
        changes=changes,
        confidence=clamp(0.62 + 0.08 * min(3, matched)),
        message=f"Applied {len(changes)} explicit intent changes from {matched} direction(s).",
    )
