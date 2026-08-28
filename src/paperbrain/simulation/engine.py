from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from random import Random

from paperbrain.domain.plans import Plan


@dataclass(frozen=True, slots=True)
class SimulationAssumptions:
    length_error_fraction: Decimal = Decimal("0.02")
    setup_time_error_fraction: Decimal = Decimal("0.10")
    machine_failure_probability_per_run: Decimal = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    scenario_index: int
    completed: bool
    failed_run_count: int
    projected_consumed_length_mm: int
    simulated_consumed_length_mm: int
    service_shortage_sheets: int


def simulate_plan(
    plan: Plan,
    *,
    scenarios: int,
    seed: int,
    assumptions: SimulationAssumptions = SimulationAssumptions(),
) -> tuple[SimulationOutcome, ...]:
    if scenarios <= 0:
        raise ValueError("Scenario count must be positive")
    rng = Random(seed)
    projected = sum(run.consumed_length_mm for run in plan.runs)
    outcomes: list[SimulationOutcome] = []
    for index in range(scenarios):
        simulated = 0
        failures = 0
        for run in plan.runs:
            length_factor = Decimal(str(rng.uniform(
                1.0 - float(assumptions.length_error_fraction),
                1.0 + float(assumptions.length_error_fraction),
            )))
            simulated += int(Decimal(run.consumed_length_mm) * length_factor)
            if rng.random() < float(assumptions.machine_failure_probability_per_run):
                failures += 1
        outcomes.append(
            SimulationOutcome(
                scenario_index=index,
                completed=failures == 0,
                failed_run_count=failures,
                projected_consumed_length_mm=projected,
                simulated_consumed_length_mm=simulated,
                service_shortage_sheets=plan.objective.service_shortage_sheets,
            )
        )
    return tuple(outcomes)
