from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from paperbrain.api.config import Settings, get_settings
from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    OrderLineSummaryResponse,
    PatternLaneResponse,
    PatternResponse,
    PlanRunResponse,
    PlanSummaryResponse,
    PlanningRequest,
    PlanningResponse,
    ReelSummaryResponse,
    ViolationResponse,
)
from paperbrain.domain.errors import NotFoundError
from paperbrain.domain.patterns import CuttingPattern
from paperbrain.domain.plans import Plan
from paperbrain.domain.policies import get_policy
from paperbrain.optimization.preprocessing import PreparedProblem

router = APIRouter(prefix="/v1/planning", tags=["planning"])


@router.post("/runs", response_model=PlanningResponse)
def create_planning_run(
    body: PlanningRequest,
    container: Annotated[Container, Depends(get_container)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanningResponse:
    policy = get_policy(body.policy_profile)
    snapshot = container.snapshot_service.create(
        policy,
        order_ids=frozenset(body.order_ids) if body.order_ids is not None else None,
    )
    result = container.planning_service.solve(
        snapshot,
        time_limit_seconds=body.time_limit_seconds or settings.default_time_limit_seconds,
        seed=body.seed,
        mode=body.mode,
    )
    container.plans.save(result.plan)
    container.planning_contexts[result.plan.id] = result.prepared
    response = _planning_response(
        result.plan,
        snapshot.checksum,
        result.validation.valid,
        result.validation.violations,
        result.prepared,
    )
    _remember_report(container, response)
    return response


@router.get("/plans", response_model=tuple[PlanSummaryResponse, ...])
def list_plans(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[PlanSummaryResponse, ...]:
    reports = container.plan_reports
    summaries: list[PlanSummaryResponse] = []
    for plan in sorted(
        container.plans.list_all(), key=lambda item: item.created_at, reverse=True
    ):
        report = reports.get(plan.id)
        objective = report.get("objective", {}) if report else {}
        validation_valid = report.get("validation_valid") if report else None
        summaries.append(
            PlanSummaryResponse(
                plan_id=plan.id,
                created_at=plan.created_at,
                status=plan.status.value,
                policy_name=plan.policy_name,
                run_count=len(plan.runs),
                validation_valid=validation_valid,
                material_loss_minor=int(objective.get("material_loss_minor", 0)),
                fresh_reels_opened=int(objective.get("fresh_reels_opened", 0)),
                service_shortage_sheets=int(
                    objective.get("service_shortage_sheets", 0)
                ),
                executed=plan.id in container.executed_plans,
            )
        )
    return tuple(summaries)


@router.get("/plans/{plan_id}", response_model=PlanningResponse)
def get_plan(
    plan_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> PlanningResponse:
    plan = container.plans.get(plan_id)
    stored = container.plan_reports.get(plan_id)
    if stored is not None:
        response = PlanningResponse.model_validate(stored)
        response.executed = plan_id in container.executed_plans
        return response
    prepared = container.planning_contexts.get(plan_id)
    if prepared is None:
        raise NotFoundError(f"Planning context for plan {plan_id} was not found")
    validation = container.planning_service.validate(plan, prepared)
    response = _planning_response(
        plan,
        prepared.snapshot.checksum,
        validation.valid,
        validation.violations,
        prepared,
    )
    _remember_report(container, response)
    return response


def _remember_report(container: Container, response: PlanningResponse) -> None:
    container.plan_reports[response.plan_id] = response.model_dump(mode="json")


def _planning_response(
    plan: Plan,
    snapshot_checksum: str,
    validation_valid: bool,
    violations: Any,
    prepared: PreparedProblem,
) -> PlanningResponse:
    solver = asdict(plan.solver)
    solver = {key: _json_value(value) for key, value in solver.items()}
    pattern_map = prepared.pattern_map
    used_patterns = _used_patterns(plan, pattern_map)
    return PlanningResponse(
        plan_id=plan.id,
        snapshot_id=plan.snapshot_id,
        snapshot_checksum=snapshot_checksum,
        status=plan.status.value if hasattr(plan.status, "value") else plan.status,
        policy_name=plan.policy_name,
        objective=asdict(plan.objective),
        solver=solver,
        runs=tuple(PlanRunResponse.model_validate(run) for run in plan.runs),
        validation_valid=validation_valid,
        violations=tuple(
            ViolationResponse(
                code=item.code,
                message=item.message,
                field=item.field,
                context=item.context,
            )
            for item in violations
        ),
        warnings=plan.warnings,
        required_confirmations=plan.required_confirmations,
        created_at=plan.created_at,
        patterns=tuple(
            PatternResponse(
                id=pattern.id,
                machine_id=pattern.machine_id,
                crosscut_length_mm=pattern.crosscut_length_mm,
                lanes=tuple(
                    PatternLaneResponse(
                        order_line_id=lane.order_line_id,
                        start_mm=lane.start_mm,
                        width_mm=lane.width_mm,
                        position=lane.position,
                    )
                    for lane in pattern.lanes
                ),
                left_trim_mm=pattern.left_trim_mm,
                right_trim_mm=pattern.right_trim_mm,
                kerf_total_mm=pattern.kerf_total_mm,
                usable_width_mm=pattern.usable_width_mm,
            )
            for pattern in used_patterns.values()
        ),
        order_lines=tuple(
            OrderLineSummaryResponse.model_validate(line)
            for line in prepared.snapshot.order_lines
        ),
        reels=tuple(
            ReelSummaryResponse(
                id=reel.id,
                reel_code=reel.reel_code,
                nominal_width_mm=reel.nominal_width_mm,
                state=reel.state.value if hasattr(reel.state, "value") else reel.state,
            )
            for reel in prepared.snapshot.reels
        ),
    )


def _used_patterns(
    plan: Plan, pattern_map: dict[UUID, CuttingPattern]
) -> dict[UUID, CuttingPattern]:
    used: dict[UUID, CuttingPattern] = {}
    for run in plan.runs:
        pattern = pattern_map.get(run.pattern_id)
        if pattern is not None:
            used[pattern.id] = pattern
    return used


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
