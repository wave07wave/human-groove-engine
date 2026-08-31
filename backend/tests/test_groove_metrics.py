import pytest
from conftest import intent, meter

from app.analysis.metrics import (
    measure_interlock,
    measure_omission,
    measure_phrase_development,
    measure_repetition,
)
from app.engine.generator import generate_pattern
from app.models.event import InstrumentID


def _pattern():
    return generate_pattern(
        bpm=105,
        bars=4,
        meter=meter(),
        intent=intent(),
        seed=141,
        performance_mode="rule",
        render_profile="off",
    )


def _event(template, *, event_id: str, bar: int, local: int, instrument, velocity=90):
    return template.model_copy(
        update={
            "event_id": event_id,
            "instrument": instrument,
            "grid_tick": bar * 4 * 960 + local,
            "velocity": velocity,
        }
    )


def test_repetition_recognizes_a_returning_abab_motif():
    source = _pattern()
    template = source.events[0]
    events = [
        _event(template, event_id="a-0", bar=0, local=0, instrument=InstrumentID.KICK),
        _event(template, event_id="b-1", bar=1, local=960, instrument=InstrumentID.SNARE),
        _event(template, event_id="a-2", bar=2, local=0, instrument=InstrumentID.KICK),
        _event(template, event_id="b-3", bar=3, local=960, instrument=InstrumentID.SNARE),
    ]
    pattern = source.model_copy(update={"events": events})

    assert measure_repetition(pattern) == pytest.approx(2 / 3)


def test_omission_measures_missing_established_strong_kick_positions():
    source = _pattern()
    template = source.events[0]
    full = [
        _event(
            template,
            event_id=f"kick-{bar}-{local}",
            bar=bar,
            local=local,
            instrument=InstrumentID.KICK,
        )
        for bar in range(4)
        for local in (0, 2 * 960)
    ]
    omitted = [
        event
        for event in full
        if not (event.grid_tick // (4 * 960) in (1, 2) and event.grid_tick % (4 * 960) == 2 * 960)
    ]

    assert measure_omission(source.model_copy(update={"events": full})) == 0
    assert measure_omission(source.model_copy(update={"events": omitted})) == 0.5


def test_phrase_development_detects_an_energy_arch_not_flat_loudness():
    source = _pattern()
    template = source.events[0]

    def with_velocities(values: list[int]):
        return source.model_copy(
            update={
                "events": [
                    _event(
                        template,
                        event_id=f"energy-{bar}",
                        bar=bar,
                        local=0,
                        instrument=InstrumentID.CLOSED_HAT,
                        velocity=velocity,
                    )
                    for bar, velocity in enumerate(values)
                ]
            }
        )

    flat = measure_phrase_development(with_velocities([72, 72, 72, 72]))
    arch = measure_phrase_development(with_velocities([40, 112, 112, 40]))
    assert flat == 0
    assert arch > 0.8


def test_interlock_rewards_drum_call_and_response_not_an_internal_bass_placeholder():
    source = _pattern()
    template = source.events[0]
    kicks = [
        _event(template, event_id=f"kick-{bar}", bar=bar, local=0, instrument=InstrumentID.KICK)
        for bar in range(4)
    ]
    snares = [
        _event(
            template, event_id=f"snare-{bar}", bar=bar, local=2 * 960, instrument=InstrumentID.SNARE
        )
        for bar in range(4)
    ]
    responsive_hats = [
        _event(
            template,
            event_id=f"reply-{bar}",
            bar=bar,
            local=240,
            instrument=InstrumentID.CLOSED_HAT,
        )
        for bar in range(4)
    ] + [
        _event(
            template,
            event_id=f"pickup-{bar}",
            bar=bar,
            local=2 * 960 - 240,
            instrument=InstrumentID.OPEN_HAT,
        )
        for bar in range(4)
    ]
    unrelated_hats = [
        _event(
            template,
            event_id=f"unrelated-{bar}-{index}",
            bar=bar,
            local=local,
            instrument=InstrumentID.CLOSED_HAT,
        )
        for bar in range(4)
        for index, local in enumerate((480, 1_440))
    ]
    responsive = source.model_copy(update={"events": kicks + snares + responsive_hats})
    unrelated = source.model_copy(update={"events": kicks + snares + unrelated_hats})
    with_internal_bass = responsive.model_copy(
        update={
            "events": responsive.events
            + [
                _event(
                    template, event_id=f"bass-{bar}", bar=bar, local=0, instrument=InstrumentID.BASS
                )
                for bar in range(4)
            ]
        }
    )

    assert measure_interlock(responsive) > measure_interlock(unrelated)
    assert measure_interlock(with_internal_bass) == measure_interlock(responsive)
