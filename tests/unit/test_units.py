from decimal import Decimal

import pytest

from paperbrain.domain.errors import DomainError
from paperbrain.domain.units import Gsm, MassKg, WidthMm, estimate_length_from_mass, sheet_mass_kg


def test_length_estimate_from_mass_uses_canonical_units() -> None:
    estimate = estimate_length_from_mass(MassKg(Decimal("3035")), WidthMm(2110), Gsm(Decimal("210")))
    assert 6_840_000 <= estimate.central.value <= 6_860_000
    assert estimate.low.value < estimate.central.value < estimate.high.value


def test_sheet_mass() -> None:
    assert sheet_mass_kg(1000, 1000, Decimal("250"), 4) == Decimal("1")


def test_invalid_width_is_rejected() -> None:
    with pytest.raises(DomainError):
        WidthMm(0)
