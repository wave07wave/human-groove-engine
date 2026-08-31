"""Deterministic phrase interventions used for matched candidate comparisons."""

from __future__ import annotations

from app.config import PPQ
from app.models.event import EventRole, InstrumentID
from app.models.pattern import GroovePattern


def phrase_state(bar: int, bars: int) -> str:
    if bars <= 1:
        return "re-entry"
    if bar == 0:
        return "establish"
    if bar == bars - 1:
        return "re-entry"
    if bar == bars - 2:
        return "release"
    return "reinforce" if bar % 3 else "challenge"


def apply_embodied_operators(pattern: GroovePattern) -> str:
    """Apply bounded removal/relabeling operators without moving protected anchors.

    Generation already creates musical material. These edits create transparent,
    reproducible intervention arms rather than a second uncontrolled random engine.
    """
    strength = pattern.intent.embodied.challenge
    renewal = pattern.intent.embodied.renewal
    if strength < 0.34 and renewal < 0.34:
        return "baseline"
    events = list(pattern.events)
    removed: set[str] = set()
    relabeled: dict[str, EventRole] = {}
    for event in events:
        bar = event.grid_tick // pattern.meter.bar_ticks
        local = event.grid_tick % pattern.meter.bar_ticks
        state = phrase_state(bar, pattern.bars)
        # Controlled challenge: make one existing offbeat event legible as a violation.
        if strength >= 0.34 and state == "challenge" and local % PPQ not in (0,):
            if event.instrument in (
                InstrumentID.KICK,
                InstrumentID.PERCUSSION,
                InstrumentID.CLOSED_HAT,
            ):
                relabeled.setdefault(event.event_id, EventRole.VIOLATION)
        # Release removes ornaments, never the downbeat kick or a recovery event.
        if renewal >= 0.5 and state == "release":
            if (
                event.instrument in (InstrumentID.PERCUSSION, InstrumentID.OPEN_HAT)
                or event.primary_role == EventRole.DECORATION
            ):
                removed.add(event.event_id)
        # A higher arm creates a deliberate omission only away from bar starts.
        if strength >= 0.67 and state == "challenge" and event.instrument == InstrumentID.KICK:
            if local not in (0,) and event.primary_role == EventRole.ANCHOR:
                removed.add(event.event_id)
    pattern.events = [
        event.model_copy(update={"primary_role": relabeled.get(event.event_id, event.primary_role)})
        for event in events
        if event.event_id not in removed
    ]
    pattern.events.sort(key=lambda event: (event.grid_tick, event.instrument.value, event.event_id))
    return (
        "challenge-high"
        if strength >= 0.67
        else "renewal"
        if renewal >= 0.5
        else "challenge-medium"
    )
