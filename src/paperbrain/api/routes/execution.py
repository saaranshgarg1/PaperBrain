from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import ReconciliationRequest, ReconciliationResponse
from paperbrain.domain.errors import NotFoundError
from paperbrain.execution.reconciliation import RunActuals, reconcile_material

router = APIRouter(prefix="/v1/execution", tags=["execution"])


@router.post("/reconcile", response_model=ReconciliationResponse)
def reconcile_run(
    body: ReconciliationRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ReconciliationResponse:
    known_run = any(
        run.id == body.run_id
        for plan in container.plans.list_all()
        for run in plan.runs
    )
    if not known_run:
        raise NotFoundError(f"Run {body.run_id} was not found")
    values = body.model_dump(exclude={"tolerance_fraction"})
    actuals = RunActuals(**values)
    balance = reconcile_material(actuals, tolerance_fraction=body.tolerance_fraction)
    return ReconciliationResponse(run_id=body.run_id, **asdict(balance))