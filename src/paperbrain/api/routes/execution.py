from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    ExecutedOrderResponse,
    ExecutedRunResponse,
    ExecutePlanResponse,
    ManualExecuteResponse,
    ManualPlanRequest,
    ReconciliationRequest,
    ReconciliationResponse,
)
from paperbrain.domain.enums import OrderStatus, PlanningRunStatus
from paperbrain.domain.errors import DomainError, DomainViolation, NotFoundError
from paperbrain.domain.patterns import CuttingPattern, LanePlacement
from paperbrain.domain.plans import ObjectiveBreakdown, Plan, PlanRun, PlanRunOutput, SolverMetadata
from paperbrain.execution.reconciliation import RunActuals, reconcile_material

router = APIRouter(prefix="/v1/execution", tags=["execution"])


@router.post(
    "/manual",
    response_model=ManualExecuteResponse,
    summary="Record cuts the operator made by hand and apply them to stock and orders",
)
def record_manual_plan(
    body: ManualPlanRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ManualExecuteResponse:
    """Build a plan from the operator's description of what was actually cut.

    Each run describes one roll: which sheet sizes were slit across the width, how
    many cross-cuts, and the trims. PaperBrain validates the geometry, consumes the
    paper from each roll (leftovers stay in stock), and completes any orders whose
    required sheets were fully produced.
    """
    lines_by_id = {line.id: line for line in container.orders.list_lines()}
    machines = {machine.id: machine for machine in container.machines.list_all()}
    reels = {reel.id: reel for reel in container.reels.list_all()}

    warnings: list[str] = []
    runs: list[PlanRun] = []
    patterns: list[CuttingPattern] = []
    consumed: list[tuple[PlanRun, CuttingPattern]] = []

    for sequence, step in enumerate(body.runs):
        machine = machines.get(step.machine_id)
        if machine is None:
            raise NotFoundError(f"Machine {step.machine_id} was not found")
        reel = reels.get(step.reel_id)
        if reel is None:
            raise NotFoundError(f"Reel {step.reel_id} was not found")

        lanes: list[LanePlacement] = []
        for position, lane in enumerate(step.lanes):
            line = lines_by_id.get(lane.order_line_id)
            if line is None:
                raise NotFoundError(f"Order line {lane.order_line_id} was not found")
            if lane.width_mm != line.sheet_width_mm:
                warnings.append(
                    f"Run {sequence + 1}: strip width {lane.width_mm} mm differs from the "
                    f"{line.sheet_width_mm} mm sheet on the order"
                )
            lanes.append(
                LanePlacement(
                    orientation_id=line.order_id,
                    order_line_id=line.id,
                    start_mm=lane.start_mm,
                    width_mm=lane.width_mm,
                    position=position,
                )
            )

        usable = lane_end = max(lane.end_mm for lane in lanes)
        pattern = CuttingPattern(
            machine_id=machine.id,
            material_spec_id=reel.material_spec_id,
            crosscut_length_mm=step.crosscut_length_mm,
            lanes=tuple(lanes),
            usable_width_mm=usable,
            left_trim_mm=step.left_trim_mm,
            right_trim_mm=max(reel.nominal_width_mm - usable - step.left_trim_mm, 0),
            kerf_total_mm=0,
            setup_family="manual",
        )
        # One output row per order line: lanes for the same line pool their sheets.
        quantity_by_line: dict[UUID, int] = {}
        for lane in lanes:
            quantity_by_line[lane.order_line_id] = (
                quantity_by_line.get(lane.order_line_id, 0) + step.crosscut_count
            )
        run = PlanRun(
            reel_id=reel.id,
            reel_segment_id=UUID(int=0),
            machine_id=machine.id,
            pattern_id=pattern.id,
            crosscut_count=step.crosscut_count,
            consumed_length_mm=step.crosscut_count * step.crosscut_length_mm,
            outputs=tuple(
                PlanRunOutput(order_line_id=line_id, quantity=quantity)
                for line_id, quantity in quantity_by_line.items()
            ),
            sequence=sequence,
        )
        runs.append(run)
        patterns.append(pattern)
        consumed.append((run, pattern))

    plan = Plan(
        snapshot_id=uuid4(),
        policy_name="manual",
        runs=tuple(runs),
        objective=ObjectiveBreakdown(),
        status=PlanningRunStatus.OPTIMAL,
        solver=SolverMetadata(
            name="manual",
            version="1",
            wall_seconds=Decimal("0"),
            seed=0,
        ),
    )
    container.plans.save(plan)
    container.planning_contexts.pop(plan.id, None)

    # Persist a report so the plan shows up in history with its pattern geometry.
    report = {
        "plan_id": str(plan.id),
        "status": "optimal",
        "policy_name": "manual",
        "objective": {"patterns_activated": len(patterns)},
        "solver": {"name": "manual", "wall_seconds": 0},
        "runs": [
            {
                "id": str(run.id),
                "reel_id": str(run.reel_id),
                "machine_id": str(run.machine_id),
                "pattern_id": str(run.pattern_id),
                "crosscut_count": run.crosscut_count,
                "consumed_length_mm": run.consumed_length_mm,
                "outputs": [
                    {"order_line_id": str(o.order_line_id), "quantity": o.quantity}
                    for o in run.outputs
                ],
                "sequence": run.sequence,
            }
            for run in runs
        ],
        "patterns": [
            {
                "id": str(pattern.id),
                "machine_id": str(pattern.machine_id),
                "crosscut_length_mm": pattern.crosscut_length_mm,
                "lanes": [
                    {
                        "order_line_id": str(lane.order_line_id),
                        "start_mm": lane.start_mm,
                        "width_mm": lane.width_mm,
                        "position": lane.position,
                    }
                    for lane in pattern.lanes
                ],
                "left_trim_mm": pattern.left_trim_mm,
                "right_trim_mm": pattern.right_trim_mm,
                "kerf_total_mm": pattern.kerf_total_mm,
                "usable_width_mm": pattern.usable_width_mm,
            }
            for pattern in patterns
        ],
        "order_lines": [
            {
                "id": str(line.id),
                "sheet_width_mm": line.sheet_width_mm,
                "sheet_length_mm": line.sheet_length_mm,
                "quantity_required": line.quantity_required,
            }
            for line in lines_by_id.values()
            if any(lane.order_line_id == line.id for p in patterns for lane in p.lanes)
        ],
        "reels": [
            {
                "id": str(reel.id),
                "reel_code": reel.reel_code,
                "nominal_width_mm": reel.nominal_width_mm,
                "state": reel.state.value,
            }
            for reel in reels.values()
            if any(run.reel_id == reel.id for run in runs)
        ],
        "validation_valid": True,
        "violations": [],
        "created_at": datetime.now(UTC).isoformat(),
    }
    container.plan_reports[plan.id] = report

    # Apply the cuts to stock and orders (same machinery as executing a saved plan).
    executed_runs: list[ExecutedRunResponse] = []
    produced_by_line: dict[UUID, int] = {}
    for run in runs:
        updated = container.inventory_service.consume(
            run.reel_id, run.consumed_length_mm, actor_id=None
        )
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

    executed_orders = _complete_fulfilled_orders(container, produced_by_line)
    container.executed_plans[plan.id] = datetime.now(UTC)

    return ManualExecuteResponse(
        executed=True,
        runs=tuple(executed_runs),
        orders=tuple(executed_orders),
        produced_sheets=sum(produced_by_line.values()),
        warnings=tuple(warnings),
    )


def _complete_fulfilled_orders(
    container: Container, produced_by_line: dict[UUID, int]
) -> list[ExecutedOrderResponse]:
    lines_by_order: dict[UUID, list] = {}
    for line in container.orders.list_lines():
        lines_by_order.setdefault(line.order_id, []).append(line)

    executed_orders: list[ExecutedOrderResponse] = []
    for order in container.orders.list_all():
        if order.status not in {OrderStatus.CONFIRMED, OrderStatus.RELEASED, OrderStatus.RUNNING}:
            continue
        lines = lines_by_order.get(order.id, [])
        produced = sum(produced_by_line.get(line.id, 0) for line in lines)
        if produced == 0:
            continue
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
    return executed_orders


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

    executed_orders = _complete_fulfilled_orders(container, produced_by_line)
    container.executed_plans[plan_id] = datetime.now(UTC)
    return ExecutePlanResponse(
        executed=True,
        plan_id=plan_id,
        runs=tuple(executed_runs),
        orders=tuple(executed_orders),
        produced_sheets=sum(produced_by_line.values()),
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
