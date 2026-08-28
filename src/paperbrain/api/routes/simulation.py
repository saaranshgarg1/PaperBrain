from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    SimulationOutcomeResponse,
    SimulationRequest,
    SimulationResponse,
)
from paperbrain.simulation.engine import SimulationAssumptions, simulate_plan

router = APIRouter(prefix="/v1/simulations", tags=["simulation"])


@router.post("/plans/{plan_id}", response_model=SimulationResponse)
def simulate_saved_plan(
    plan_id: UUID,
    body: SimulationRequest,
    container: Annotated[Container, Depends(get_container)],
) -> SimulationResponse:
    plan = container.plans.get(plan_id)
    outcomes = simulate_plan(
        plan,
        scenarios=body.scenarios,
        seed=body.seed,
        assumptions=SimulationAssumptions(
            length_error_fraction=body.length_error_fraction,
            machine_failure_probability_per_run=body.machine_failure_probability_per_run,
        ),
    )
    completed = sum(1 for outcome in outcomes if outcome.completed)
    return SimulationResponse(
        plan_id=plan.id,
        scenario_count=len(outcomes),
        completion_probability=Decimal(completed) / Decimal(len(outcomes)),
        outcomes=tuple(SimulationOutcomeResponse.model_validate(item) for item in outcomes),
    )
