import re
from typing import Literal, Self

from pydantic import Field, model_validator

from latros.sources.registry import Contract

CATEGORIES: dict[str, tuple[float, float]] = {
    "HP:0040280": (1.0, 1.0),
    "HP:0040281": (0.80, 0.99),
    "HP:0040282": (0.30, 0.79),
    "HP:0040283": (0.05, 0.29),
    "HP:0040284": (0.01, 0.04),
    "HP:0040285": (0.0, 0.0),
}


class Frequency(Contract):
    kind: Literal["count", "percentage", "interval", "category", "excluded", "missing"]
    raw: str | None = None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, gt=0)
    lower: float | None = Field(default=None, ge=0, le=1)
    upper: float | None = Field(default=None, ge=0, le=1)
    category: str | None = None

    @model_validator(mode="after")
    def validate_frequency(self) -> Self:
        if self.kind == "missing":
            if any(
                x is not None
                for x in (self.lower, self.upper, self.numerator, self.denominator, self.category)
            ):
                raise ValueError("Missing frequency must not contain estimates")
            return self
        if self.lower is None or self.upper is None or self.lower > self.upper:
            raise ValueError("Nonmissing frequency requires ordered bounds")
        if self.kind == "count":
            if self.numerator is None or self.denominator is None:
                raise ValueError("Counts require k and n")
            if self.numerator > self.denominator:
                raise ValueError("Count exceeds cohort size")
            if self.lower != self.numerator / self.denominator or self.upper != self.lower:
                raise ValueError("Bounds must match k/n")
        elif self.numerator is not None or self.denominator is not None:
            raise ValueError("Counts only allowed for count frequency")
        if self.kind in {"category", "excluded"}:
            if self.category not in CATEGORIES:
                raise ValueError("Unknown frequency category")
            if (self.lower, self.upper) != CATEGORIES[self.category]:
                raise ValueError("Bounds disagree with frequency category")
        elif self.category is not None:
            raise ValueError("Category only allowed for category/excluded frequency")
        if self.kind == "excluded" and self.category != "HP:0040285":
            raise ValueError("Excluded frequency must use exclusion category")
        if self.kind == "percentage" and self.lower != self.upper:
            raise ValueError("Percentage must be a point estimate")
        return self

    def estimate(self) -> float | None:
        """Explicit planning approximation; never a diagnostic posterior.

        Counts use Beta(1,1) smoothing. Intervals/categories use their midpoint,
        with raw bounds retained in every explanation. Missing stays None.
        """
        if self.kind == "missing":
            return None
        if self.kind == "count":
            assert self.numerator is not None and self.denominator is not None
            return (self.numerator + 1) / (self.denominator + 2)
        assert self.lower is not None and self.upper is not None
        return (self.lower + self.upper) / 2


def parse_frequency(raw: str | None) -> Frequency:
    if raw is None or not raw.strip():
        return Frequency(kind="missing", raw=raw)
    value = raw.strip()
    if value in CATEGORIES:
        lower, upper = CATEGORIES[value]
        return Frequency(
            kind="excluded" if upper == 0 else "category",
            raw=raw,
            category=value,
            lower=lower,
            upper=upper,
        )
    if match := re.fullmatch(r"(\d+)\s*/\s*([1-9]\d*)", value):
        k, n = map(int, match.groups())
        return Frequency(
            kind="count", raw=raw, numerator=k, denominator=n, lower=k / n, upper=k / n
        )
    if match := re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", value):
        point = float(match[1]) / 100
        return Frequency(kind="percentage", raw=raw, lower=point, upper=point)
    if match := re.fullmatch(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%", value):
        lower, upper = (float(x) / 100 for x in match.groups())
        return Frequency(kind="interval", raw=raw, lower=lower, upper=upper)
    raise ValueError(f"Unsupported frequency: {raw!r}")
