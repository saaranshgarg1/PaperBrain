from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from paperbrain.api.config import Settings, get_settings
from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    PlanRunResponse,
    PlanningRequest,
    PlanningResponse,
    ViolationResponse,
)
from paperbrain.domain.plans import Plan
from paperbrain.domain.errors import NotFoundError
from paperbrain.domain.policies import get_policy

router = APIRouter(prefix="/v1/planning", tags=["planning"])


@router.post("/runs", response_model=PlanningResponse)
def create_planning_run(
    body: PlanningRequest,
    container: Annotated[Container, Depends(get_container)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanningResponse:
    policy = get_policy(body.policy_profile)
    snapshot = container.snapshot_service.create(policy)
    result = container.planning_service.solve(
        snapshot,
        time_limit_seconds=body.time_limit_seconds or settings.default_time_limit_seconds,
        seed=body.seed,
        mode=body.mode,
    )
    container.plans.save(result.plan)
    container.planning_contexts[result.plan.id] = result.prepared
    return _planning_response(result.plan, snapshot.checksum, result.validation)


@router.get("/plans/{plan_id}", response_model=PlanningResponse)
def get_plan(
    plan_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> PlanningResponse:
    plan = container.plans.get(plan_id)
    try:
        prepared = container.planning_contexts[plan_id]
    except KeyError as exc:
        raise NotFoundError(f"Planning context for plan {plan_id} was not found") from exc
    validation = container.planning_service.validate(plan, prepared)
    return _planning_response(plan, prepared.snapshot.checksum, validation)


def _planning_response(plan: Plan, snapshot_checksum: str, validation: Any) -> PlanningResponse:
    solver = asdict(plan.solver)
    solver = {key: _json_value(value) for key, value in solver.items()}
    return PlanningResponse(
        plan_id=plan.id,
        snapshot_id=plan.snapshot_id,
        snapshot_checksum=snapshot_checksum,
        status=plan.status,
        policy_name=plan.policy_name,
        objective=asdict(plan.objective),
        solver=solver,
        runs=tuple(PlanRunResponse.model_validate(run) for run in plan.runs),
        validation_valid=validation.valid,
        violations=tuple(
            ViolationResponse(
                code=item.code,
                message=item.message,
                field=item.field,
                context=item.context,
            )
            for item in validation.violations
        ),
        warnings=plan.warnings,
        required_confirmations=plan.required_confirmations,
    )


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)