from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RunActuals:
    run_id: UUID
    input_mass_kg: Decimal
    good_product_mass_kg: Decimal
    retained_remainder_mass_kg: Decimal
    normal_trim_mass_kg: Decimal = Decimal("0")
    damaged_edge_mass_kg: Decimal = Decimal("0")
    defect_mass_kg: Decimal = Decimal("0")
    setup_mass_kg: Decimal = Decimal("0")
    tail_mass_kg: Decimal = Decimal("0")
    overrun_waste_mass_kg: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class MaterialBalance:
    accounted_mass_kg: Decimal
    variance_mass_kg: Decimal
    variance_fraction: Decimal
    within_tolerance: bool


def reconcile_material(
    actuals: RunActuals,
    *,
    tolerance_fraction: Decimal = Decimal("0.005"),
) -> MaterialBalance:
    if actuals.input_mass_kg <= 0:
        raise ValueError("Input mass must be positive")
    components = (
        actuals.good_product_mass_kg,
        actuals.retained_remainder_mass_kg,
        actuals.normal_trim_mass_kg,
        actuals.damaged_edge_mass_kg,
        actuals.defect_mass_kg,
        actuals.setup_mass_kg,
        actuals.tail_mass_kg,
        actuals.overrun_waste_mass_kg,
    )
    if any(component < 0 for component in components):
        raise ValueError("Material-balance components cannot be negative")
    accounted = sum(components, Decimal("0"))
    variance = actuals.input_mass_kg - accounted
    fraction = abs(variance) / actuals.input_mass_kg
    return MaterialBalance(
        accounted_mass_kg=accounted,
        variance_mass_kg=variance,
        variance_fraction=fraction,
        within_tolerance=fraction <= tolerance_fraction,
    )
