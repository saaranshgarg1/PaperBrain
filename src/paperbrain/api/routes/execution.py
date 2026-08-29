from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    ExecutedOrderResponse,
    ExecutedRunResponse,
    ExecutePlanResponse,
    ReconciliationRequest,
    ReconciliationResponse,
)
from paperbrain.domain.enums import OrderStatus
from paperbrain.domain.errors import DomainError, DomainViolation, NotFoundError
from paperbrain.execution.reconciliation import RunActuals, reconcile_material

router = APIRouter(prefix="/v1/execution", tags=["execution"])


@router.post(
    "/plans/{plan_id}/execute",
    response_model=ExecutePlanResponse,
    summary="Carry out a plan on the shop floor: consume paper, finish orders",
)
def execute_plan(
    plan_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> ExecutePlanResponse:
    if plan_id in container.executed_plans:
        raise DomainError(
            DomainViolation("PLAN_ALREADY_EXECUTED", "This plan has already been carried out")
        )
    plan = container.plans.get(plan_id)

    reel_by_id = {reel.id: reel.reel_code for reel in container.reels.list_all()}
    executed_runs: list[ExecutedRunResponse] = []
    produced_by_line: dict[UUID, int] = {}
    for run in sorted(plan.runs, key=lambda item: item.sequence):
        updated = container.inventory_service.consume(run.reel_id, run.consumed_length_mm, actor_id=None)
        executed_runs.append(
            ExecutedRunResponse(
                reel_id=updated.id,
                reel_code=updated.reel_code,
                consumed_length_mm=run.consumed_length_mm,
                remaining_length_mm=updated.remaining_length_mm,
                reel_state=updated.state.value,
            )
        )
        for output in run.outputs:
            produced_by_line[output.order_line_id] = (
                produced_by_line.get(output.order_line_id, 0) + output.quantity
            )

    lines_by_order: dict[UUID, list] = {}
    for line in container.orders.list_lines():
        lines_by_order.setdefault(line.order_id, []).append(line)

    executed_orders: list[ExecutedOrderResponse] = []
    produced_sheets = 0
    for order in container.orders.list_all():
        if order.status not in {OrderStatus.CONFIRMED, OrderStatus.RELEASED, OrderStatus.RUNNING}:
            continue
        lines = lines_by_order.get(order.id, [])
        produced = sum(produced_by_line.get(line.id, 0) for line in lines)
        if produced == 0:
            continue
        produced_sheets += produced
        completed = all(
            produced_by_line.get(line.id, 0) >= line.quantity_required for line in lines
        )
        if completed:
            updated_order = replace(order, status=OrderStatus.COMPLETE, version=order.version + 1)
            container.orders.save(updated_order, tuple(lines))
        executed_orders.append(
            ExecutedOrderResponse(
                order_id=order.id,
                external_id=order.external_id,
                completed=completed,
            )
        )

    container.executed_plans[plan_id] = datetime.now(UTC)
    return ExecutePlanResponse(
        executed=True,
        plan_id=plan_id,
        runs=tuple(executed_runs),
        orders=tuple(executed_orders),
        produced_sheets=produced_sheets,
    )


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
