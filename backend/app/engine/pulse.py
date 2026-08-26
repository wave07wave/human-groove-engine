from app.models.meter import MeterDefinition


def metric_gravity(meter: MeterDefinition, position_tick: int) -> float:
    """Meter-aware gravity that distinguishes simple, compound and odd meters."""
    pos = position_tick % meter.bar_ticks
    unit_tick = meter.bar_ticks / sum(meter.grouping)
    cursor = 0
    boundaries = {0: 1.0}
    for index, group in enumerate(meter.grouping):
        boundaries[int(cursor * unit_tick)] = 0.82 if index else 1.0
        cursor += group
    if pos in boundaries:
        return boundaries[pos]
    if pos % 960 == 0:
        return 0.68
    if pos % 480 == 0:
        return 0.48
    if pos % 240 == 0:
        return 0.26
    return 0.12


def virtual_beat_map(meter: MeterDefinition, bars: int, stability: float) -> list[float]:
    step = 240
    return [
        min(0.98, 0.1 + metric_gravity(meter, tick) * (0.55 + 0.35 * stability))
        for tick in range(0, bars * meter.bar_ticks, step)
    ]


def strong_positions(meter: MeterDefinition) -> list[int]:
    unit = meter.bar_ticks / sum(meter.grouping)
    cursor = 0
    result = []
    for group in meter.grouping:
        result.append(int(cursor * unit))
        cursor += group
    return result
