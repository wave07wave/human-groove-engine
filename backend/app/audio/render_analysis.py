from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import PPQ
from app.models.analysis import RenderedAudioAnalysis
from app.models.event import EventRole, InstrumentID
from app.models.pattern import GroovePattern

if TYPE_CHECKING:
    from app.bass.models import BassPattern

PROFILE_DIRECTORY = Path(__file__).resolve().parent / "profiles"
MAX_ANALYZED_BARS = 8


class InstrumentRenderProfile(BaseModel):
    oscillator: Literal["sine", "triangle", "noise"]
    frequency_hz: float = Field(gt=20, le=4_000)
    attack_ms: float = Field(ge=0.1, le=100)
    decay_ms: float = Field(ge=5, le=2_000)
    gain: float = Field(gt=0, le=2)
    transient_mix: float = Field(ge=0, le=1)
    noise_mix: float = Field(ge=0, le=1)
    band: Literal["low", "mid", "high"]
    low_end_weight: float = Field(ge=0, le=1)


class RenderProfile(BaseModel):
    profile_id: str
    version: str
    display_name: str
    sample_rate: int = Field(ge=8_000, le=48_000)
    instruments: dict[str, InstrumentRenderProfile]

    @model_validator(mode="after")
    def complete_instrument_set(self) -> "RenderProfile":
        expected = {instrument.value for instrument in InstrumentID}
        if not expected.issubset(self.instruments):
            raise ValueError("render profile is missing supported instruments")
        return self


def available_render_profiles() -> list[dict[str, str | int]]:
    profiles = []
    for path in sorted(PROFILE_DIRECTORY.glob("*.json")):
        profile = load_render_profile(path.stem)
        if profile is not None:
            profiles.append(
                {
                    "profile_id": profile.profile_id,
                    "version": profile.version,
                    "display_name": profile.display_name,
                    "sample_rate": profile.sample_rate,
                }
            )
    return profiles


@lru_cache(maxsize=8)
def load_render_profile(profile_id: str) -> RenderProfile | None:
    if not profile_id or Path(profile_id).name != profile_id:
        return None
    try:
        payload = json.loads((PROFILE_DIRECTORY / f"{profile_id}.json").read_text(encoding="utf-8"))
        profile = RenderProfile.model_validate(payload)
        return profile if profile.profile_id == profile_id else None
    except (OSError, json.JSONDecodeError, ValidationError, ValueError, TypeError):
        return None


def _selected_bars(total: int) -> list[int]:
    if total <= MAX_ANALYZED_BARS:
        return list(range(total))
    return sorted({round(index * (total - 1) / (MAX_ANALYZED_BARS - 1)) for index in range(8)})


def _oscillator(
    profile: InstrumentRenderProfile,
    event_id: str,
    samples: int,
    sample_rate: int,
    frequency_hz: float | None = None,
) -> np.ndarray:
    time = np.arange(samples, dtype=np.float32) / sample_rate
    phase = 2 * np.pi * (frequency_hz or profile.frequency_hz) * time
    if profile.oscillator == "triangle":
        tonal = 2 / np.pi * np.arcsin(np.sin(phase))
    elif profile.oscillator == "noise":
        seed = int.from_bytes(hashlib.sha256(event_id.encode()).digest()[:8], "big")
        tonal = np.random.Generator(np.random.PCG64DXSM(seed)).normal(0, 0.55, samples)
    else:
        tonal = np.sin(phase)
    attack_seconds = profile.attack_ms / 1_000
    decay_seconds = profile.decay_ms / 1_000
    envelope = (1 - np.exp(-time / attack_seconds)) * np.exp(-time / decay_seconds)
    transient = np.sin(phase * 3.7) * np.exp(-time / 0.004)
    if profile.noise_mix:
        seed = int.from_bytes(hashlib.sha256(f"noise:{event_id}".encode()).digest()[:8], "big")
        noise = np.random.Generator(np.random.PCG64DXSM(seed)).normal(0, 0.35, samples)
    else:
        noise = np.zeros(samples)
    body = tonal * (1 - profile.noise_mix) + noise * profile.noise_mix
    return profile.gain * (body * envelope + transient * profile.transient_mix)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def reference_velocity_gain(velocity: int) -> float:
    """Match the monotonic acoustic-preview velocity response."""
    normalized = max(0.0, min(1.0, velocity / 127))
    return normalized**1.25


def _event_seconds(event, pattern: GroovePattern) -> float:
    return event.performed_tick * 60 / (pattern.bpm * PPQ) + event.micro_offset_us / 1_000_000


def _open_hat_choke_seconds(pattern: GroovePattern) -> dict[str, float]:
    """Map each open hat to the exact performed time of its later choke hit."""
    hat_events = sorted(
        (
            (_event_seconds(event, pattern), event)
            for event in pattern.events
            if event.choke_group == "hihat"
            and event.instrument in (InstrumentID.CLOSED_HAT, InstrumentID.OPEN_HAT)
        ),
        key=lambda item: (item[0], item[1].event_id),
    )
    choke_times: dict[str, float] = {}
    active_open: tuple[float, str] | None = None
    for onset, event in hat_events:
        if active_open is not None and onset > active_open[0]:
            choke_times[active_open[1]] = onset
            active_open = None
        if event.instrument == InstrumentID.OPEN_HAT:
            active_open = (onset, event.event_id)
    return choke_times


def analyze_reference_render(
    pattern: GroovePattern, bass_pattern: BassPattern | None = None
) -> RenderedAudioAnalysis | None:
    profile = load_render_profile(pattern.metadata.render_profile)
    if profile is None:
        return None
    bars = _selected_bars(pattern.bars)
    bar_seconds = pattern.meter.bar_ticks * 60 / (pattern.bpm * PPQ)
    segment_seconds = bar_seconds + 0.55
    total_samples = max(1, math.ceil(len(bars) * segment_seconds * profile.sample_rate))
    signal = np.zeros(total_samples, dtype=np.float32)
    band_energy = {
        band: np.zeros(total_samples, dtype=np.float32) for band in ("low", "mid", "high")
    }
    kick_low = np.zeros(total_samples, dtype=np.float32)
    bass_low = np.zeros(total_samples, dtype=np.float32)
    attacks: list[tuple[str, int, np.ndarray, float]] = []
    rendered_events = 0
    selected_index = {bar: index for index, bar in enumerate(bars)}
    max_tail_samples = round(0.5 * profile.sample_rate)
    open_hat_choke_times = _open_hat_choke_seconds(pattern)

    render_events = [
        (event, event.instrument, event.primary_role)
        for event in pattern.events
        if bass_pattern is None or event.instrument != InstrumentID.BASS
    ]
    if bass_pattern is not None:
        render_events.extend((event, InstrumentID.BASS, None) for event in bass_pattern.events)

    for event, instrument_id, role in render_events:
        bar = event.grid_tick // pattern.meter.bar_ticks
        if bar not in selected_index:
            continue
        instrument = profile.instruments[instrument_id.value]
        bar_tick = bar * pattern.meter.bar_ticks
        local_seconds = (event.grid_tick + event.structural_offset_tick - bar_tick) * 60 / (
            pattern.bpm * PPQ
        ) + event.micro_offset_us / 1_000_000
        start = round(
            (selected_index[bar] * segment_seconds + max(0, local_seconds)) * profile.sample_rate
        )
        event_seconds = max(
            instrument.decay_ms / 1_000,
            event.duration_tick * 60 / (pattern.bpm * PPQ),
        )
        choke_time = open_hat_choke_times.get(event.event_id)
        if choke_time is not None:
            event_seconds = min(
                event_seconds,
                max(0.008, choke_time - _event_seconds(event, pattern)),
            )
        samples = min(max_tail_samples, max(8, round(event_seconds * profile.sample_rate)))
        stop = min(total_samples, start + samples)
        if stop <= start:
            continue
        velocity_gain = reference_velocity_gain(event.velocity)
        frequency_hz = None
        if instrument_id == InstrumentID.BASS and event.pitch is not None:
            frequency_hz = 440 * 2 ** ((event.pitch - 69) / 12)
        wave = _oscillator(
            instrument,
            event.event_id,
            stop - start,
            profile.sample_rate,
            frequency_hz,
        )
        wave = wave.astype(np.float32) * velocity_gain
        signal[start:stop] += wave
        energy = wave * wave
        band_energy[instrument.band][start:stop] += energy
        if instrument_id == InstrumentID.KICK:
            kick_low[start:stop] += energy * instrument.low_end_weight
        elif instrument_id == InstrumentID.BASS:
            bass_low[start:stop] += energy * instrument.low_end_weight
        role_weight = 0.35 if role == EventRole.GHOST else 1.0
        attacks.append((instrument.band, start, energy, role_weight))
        rendered_events += 1

    masking_values = []
    masking_weights = []
    attack_window = max(8, round(profile.sample_rate * 0.012))
    for band, start, own_energy, weight in attacks:
        width = min(attack_window, len(own_energy), total_samples - start)
        own = float(np.sum(own_energy[:width]))
        total = float(np.sum(band_energy[band][start : start + width]))
        background = max(0.0, total - own)
        masking_values.append(background / max(1e-9, background + own))
        masking_weights.append(weight)
    transient_masking = (
        float(np.average(masking_values, weights=masking_weights)) if masking_values else 0.0
    )
    kick_energy = float(np.sum(kick_low))
    bass_energy = float(np.sum(bass_low))
    collision_applicable = kick_energy > 1e-8 and bass_energy > 1e-8
    collision = (
        float(2 * np.sum(np.minimum(kick_low, bass_low)) / (kick_energy + bass_energy))
        if collision_applicable
        else 0.0
    )
    peak = float(np.max(np.abs(signal))) if len(signal) else 0.0
    # 50–100 Hz is an ordinary audible low-band descriptor. It is intentionally
    # not an infrasound synthesizer or a claim about a listener's body.
    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(len(signal), 1 / profile.sample_rate)
    low_mask = (frequencies >= 50) & (frequencies <= 100)
    full_energy = float(np.sum(np.abs(spectrum) ** 2))
    low_energy = float(np.sum(np.abs(spectrum[low_mask]) ** 2))
    low_frequency_flux = _clamp(low_energy / max(1e-9, full_energy) * 6.0)
    onset_window = max(1, round(profile.sample_rate * 0.035))
    kick_starts = []
    bass_starts = []
    for event, instrument_id, _role in render_events:
        if instrument_id not in (InstrumentID.KICK, InstrumentID.BASS):
            continue
        bar = event.grid_tick // pattern.meter.bar_ticks
        if bar not in selected_index:
            continue
        local_seconds = (
            event.grid_tick + event.structural_offset_tick - bar * pattern.meter.bar_ticks
        ) * 60 / (pattern.bpm * PPQ) + event.micro_offset_us / 1_000_000
        start = round(
            (selected_index[bar] * segment_seconds + max(0, local_seconds)) * profile.sample_rate
        )
        (kick_starts if instrument_id == InstrumentID.KICK else bass_starts).append(start)
    if kick_starts and bass_starts:
        matched = sum(
            any(abs(kick - bass) <= onset_window for bass in bass_starts) for kick in kick_starts
        )
        kick_bass_onset_coherence = _clamp(matched / max(len(kick_starts), len(bass_starts)))
    else:
        kick_bass_onset_coherence = None
    envelope_window = max(1, round(profile.sample_rate * 0.06))
    low_energy_signal = kick_low + bass_low
    blocks = [
        float(np.mean(low_energy_signal[index : index + envelope_window]))
        for index in range(0, len(low_energy_signal), envelope_window)
    ]
    low_end_envelope_cycle = (
        _clamp(float(np.std(blocks)) / (float(np.mean(blocks)) + 1e-9)) if blocks else None
    )
    headroom = _clamp((1.25 - peak) / 0.55)
    onset_clarity = _clamp(1 - transient_masking)
    render_quality = _clamp(
        0.5 * onset_clarity
        + 0.3 * (1 - collision if collision_applicable else onset_clarity)
        + 0.15 * headroom
        + 0.05 * low_frequency_flux
    )
    return RenderedAudioAnalysis(
        scope="joint" if bass_pattern is not None else "groove",
        profile_id=profile.profile_id,
        profile_version=profile.version,
        sample_rate=profile.sample_rate,
        analyzed_bars=bars,
        rendered_events=rendered_events,
        low_end_collision=_clamp(collision),
        low_end_collision_applicable=collision_applicable,
        transient_masking=_clamp(transient_masking),
        onset_clarity=onset_clarity,
        headroom=headroom,
        render_quality=render_quality,
        low_frequency_flux=low_frequency_flux,
        kick_bass_onset_coherence=kick_bass_onset_coherence,
        low_end_envelope_cycle=low_end_envelope_cycle,
        confidence=0.58,
        caveat="Deterministic reference-synth render, not analysis of recorded or exported audio.",
    )
