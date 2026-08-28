from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import MachineCreate, MachineResponse
from paperbrain.domain.machines import Machine

router = APIRouter(prefix="/v1/machines", tags=["machines"])


@router.post("", response_model=MachineResponse, status_code=status.HTTP_201_CREATED)
def create_machine(
    body: MachineCreate,
    container: Annotated[Container, Depends(get_container)],
) -> Machine:
    machine = Machine(**body.model_dump())
    container.machines.save(machine)
    return machine


@router.get("", response_model=tuple[MachineResponse, ...])
def list_machines(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[Machine, ...]:
    return container.machines.list_all()
