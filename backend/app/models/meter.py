from pydantic import BaseModel, Field, model_validator

from app.config import PPQ


class MeterDefinition(BaseModel):
    numerator: int = Field(ge=1, le=32)
    denominator: int = Field(default=4)
    grouping: list[int]
    subdivisions_per_quarter: int = Field(default=4, ge=1, le=16)

    @model_validator(mode="after")
    def validate_meter(self) -> "MeterDefinition":
        if self.denominator not in (2, 4, 8, 16):
            raise ValueError("denominator must be 2, 4, 8 or 16")
        if not self.grouping or any(x <= 0 for x in self.grouping):
            raise ValueError("grouping values must be positive")
        valid_sums = {self.numerator, self.numerator * 2}
        if sum(self.grouping) not in valid_sums:
            raise ValueError(f"grouping must sum to one of {sorted(valid_sums)}")
        return self

    @property
    def bar_ticks(self) -> int:
        return int(self.numerator * PPQ * 4 / self.denominator)

    @classmethod
    def from_name(cls, name: str) -> "MeterDefinition":
        options = {
            "4/4": cls(numerator=4, denominator=4, grouping=[2, 2]),
            "3/4": cls(numerator=3, denominator=4, grouping=[2, 2, 2]),
            "5/4": cls(numerator=5, denominator=4, grouping=[3, 2]),
            "5/8": cls(numerator=5, denominator=8, grouping=[3, 2]),
            "6/8": cls(numerator=6, denominator=8, grouping=[3, 3]),
            "12/8": cls(numerator=12, denominator=8, grouping=[3, 3, 3, 3]),
        }
        if name not in options:
            raise ValueError(f"unsupported meter: {name}")
        return options[name]
