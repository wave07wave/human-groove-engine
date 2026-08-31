import pytest
from pydantic import ValidationError

from app.engine.pulse import metric_gravity, strong_positions
from app.models.event import GrooveEvent, InstrumentID
from app.models.meter import MeterDefinition


@pytest.mark.parametrize(
    "name,ticks,groups",
    [
        ("4/4", 3840, [0, 1920]),
        ("3/4", 2880, [0, 960, 1920]),
        ("5/4", 4800, [0, 2880]),
        ("5/8", 2400, [0, 1440]),
        ("6/8", 2880, [0, 1440]),
        ("12/8", 5760, [0, 1440, 2880, 4320]),
    ],
)
def test_supported_meters(name, ticks, groups):
    value = MeterDefinition.from_name(name)
    assert value.bar_ticks == ticks
    assert strong_positions(value) == groups


def test_compound_meter_is_not_three_four():
    six = MeterDefinition.from_name("6/8")
    three = MeterDefinition.from_name("3/4")
    assert strong_positions(six) != strong_positions(three)
    assert metric_gravity(six, 1440) > metric_gravity(three, 1440)


def test_five_four_and_five_eight_have_distinct_time_scales():
    five_four = MeterDefinition.from_name("5/4")
    five_eight = MeterDefinition.from_name("5/8")
    assert five_four.grouping == five_eight.grouping == [3, 2]
    assert five_four.bar_ticks == five_eight.bar_ticks * 2
    assert strong_positions(five_four) == [0, 2880]
    assert strong_positions(five_eight) == [0, 1440]


@pytest.mark.parametrize(
    "subdivisions,step_tick",
    [(2, 480), (3, 320), (4, 240), (6, 160), (8, 120)],
)
def test_exact_grid_resolutions(subdivisions, step_tick):
    value = MeterDefinition(
        numerator=4,
        denominator=4,
        grouping=[2, 2],
        subdivisions_per_quarter=subdivisions,
    )
    assert value.subdivision_tick == step_tick
    assert value.bar_ticks % value.subdivision_tick == 0


def test_grid_must_fit_bar_without_truncation():
    with pytest.raises(ValidationError):
        MeterDefinition(
            numerator=5,
            denominator=8,
            grouping=[3, 2],
            subdivisions_per_quarter=3,
        )


def test_event_validation_rejects_invalid_data():
    with pytest.raises(ValidationError):
        GrooveEvent(instrument=InstrumentID.KICK, grid_tick=-1, duration_tick=0, velocity=200)
