from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from paperbrain.domain.errors import DomainError, DomainViolation

DECIMAL_PI = Decimal("3.1415926535897932384626433832795028841971693993751")


def _decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True, order=True, slots=True)
class WidthMm:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise DomainError(
                DomainViolation("INVALID_WIDTH", "Width must be positive", "width_mm")
            )


@dataclass(frozen=True, order=True, slots=True)
class LengthMm:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise DomainError(
                DomainViolation("INVALID_LENGTH", "Length cannot be negative", "length_mm")
            )


@dataclass(frozen=True, order=True, slots=True)
class MassKg:
    value: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _decimal(self.value))
        if self.value < 0:
            raise DomainError(DomainViolation("INVALID_MASS", "Mass cannot be negative", "mass_kg"))


@dataclass(frozen=True, order=True, slots=True)
class Gsm:
    value: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _decimal(self.value))
        if self.value <= 0:
            raise DomainError(DomainViolation("INVALID_GSM", "GSM must be positive", "gsm"))


@dataclass(frozen=True, slots=True)
class Money:
    minor: int
    currency: str

    def __post_init__(self) -> None:
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise DomainError(
                DomainViolation("INVALID_CURRENCY", "Currency must be a three-letter code")
            )
        object.__setattr__(self, "currency", self.currency.upper())

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise DomainError(DomainViolation("CURRENCY_MISMATCH", "Cannot add unlike currencies"))
        return Money(self.minor + other.minor, self.currency)


@dataclass(frozen=True, slots=True)
class EstimateInterval:
    central: LengthMm
    low: LengthMm
    high: LengthMm
    confidence: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _decimal(self.confidence))
        if not (self.low.value <= self.central.value <= self.high.value):
            raise DomainError(
                DomainViolation("INVALID_INTERVAL", "Estimate must be between low and high")
            )
        if not (Decimal("0") <= self.confidence <= Decimal("1")):
            raise DomainError(
                DomainViolation("INVALID_CONFIDENCE", "Confidence must be between zero and one")
            )


def estimate_length_from_mass(
    net_mass: MassKg,
    width: WidthMm,
    gsm: Gsm,
    *,
    relative_uncertainty: Decimal = Decimal("0.02"),
) -> EstimateInterval:
    """Estimate reel length in millimetres from net paper mass."""
    uncertainty = _decimal(relative_uncertainty)
    if not (Decimal("0") <= uncertainty < Decimal("1")):
        raise DomainError(
            DomainViolation("INVALID_UNCERTAINTY", "Relative uncertainty must be in [0, 1)")
        )
    length = (
        Decimal("1000000000") * net_mass.value / (Decimal(width.value) * gsm.value)
    ).to_integral_value(rounding=ROUND_FLOOR)
    central = int(length)
    low = int((length * (Decimal("1") - uncertainty)).to_integral_value(rounding=ROUND_FLOOR))
    high = int((length * (Decimal("1") + uncertainty)).to_integral_value(rounding=ROUND_FLOOR))
    return EstimateInterval(
        central=LengthMm(central),
        low=LengthMm(low),
        high=LengthMm(high),
        confidence=max(Decimal("0"), Decimal("1") - uncertainty),
    )


def estimate_length_from_diameter(
    outer_diameter_mm: Decimal | int | float | str,
    core_diameter_mm: Decimal | int | float | str,
    caliper_mm: Decimal | int | float | str,
    *,
    relative_uncertainty: Decimal = Decimal("0.05"),
) -> EstimateInterval:
    outer = _decimal(outer_diameter_mm)
    core = _decimal(core_diameter_mm)
    caliper = _decimal(caliper_mm)
    uncertainty = _decimal(relative_uncertainty)
    if outer <= core or core <= 0 or caliper <= 0:
        raise DomainError(
            DomainViolation(
                "INVALID_DIAMETER_INPUT",
                "Outer diameter must exceed a positive core diameter and caliper",
            )
        )
    length = (DECIMAL_PI * (outer * outer - core * core) / (Decimal("4") * caliper)).to_integral_value(
        rounding=ROUND_FLOOR
    )
    central = int(length)
    low = int((length * (Decimal("1") - uncertainty)).to_integral_value(rounding=ROUND_FLOOR))
    high = int((length * (Decimal("1") + uncertainty)).to_integral_value(rounding=ROUND_FLOOR))
    return EstimateInterval(
        central=LengthMm(central),
        low=LengthMm(low),
        high=LengthMm(high),
        confidence=max(Decimal("0"), Decimal("1") - uncertainty),
    )


def sheet_mass_kg(width_mm: int, length_mm: int, gsm: Decimal, quantity: int = 1) -> Decimal:
    if width_mm <= 0 or length_mm <= 0 or quantity < 0 or gsm <= 0:
        raise DomainError(DomainViolation("INVALID_SHEET_MASS_INPUT", "Invalid sheet mass input"))
    return Decimal(width_mm * length_mm * quantity) * gsm / Decimal("1000000000")
