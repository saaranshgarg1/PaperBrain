from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from random import Random
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ForecastDemand:
    order_family_id: UUID
    order_line_template_id: UUID
    expected_quantity: int
    occurrence_probability: Decimal
    quantity_low: int
    quantity_high: int


@dataclass(frozen=True, slots=True)
class DemandScenario:
    index: int
    quantities: dict[UUID, int]
    probability: Decimal


def generate_scenarios(
    forecasts: tuple[ForecastDemand, ...],
    *,
    count: int,
    seed: int,
) -> tuple[DemandScenario, ...]:
    if count <= 0:
        raise ValueError("Scenario count must be positive")
    rng = Random(seed)
    probability = Decimal("1") / Decimal(count)
    scenarios: list[DemandScenario] = []
    for index in range(count):
        quantities: dict[UUID, int] = {}
        for forecast in forecasts:
            if rng.random() > float(forecast.occurrence_probability):
                quantities[forecast.order_line_template_id] = 0
                continue
            quantities[forecast.order_line_template_id] = rng.randint(
                forecast.quantity_low,
                forecast.quantity_high,
            )
        scenarios.append(DemandScenario(index=index, quantities=quantities, probability=probability))
    return tuple(scenarios)
