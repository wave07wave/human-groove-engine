from app.models.groove import GrooveIntent
from app.models.meter import MeterDefinition


def intent(**changes: float) -> GrooveIntent:
    value = GrooveIntent()
    for key, setting in changes.items():
        setattr(value.target_dna, key, setting)
    return value


def meter(name: str = "4/4") -> MeterDefinition:
    return MeterDefinition.from_name(name)
