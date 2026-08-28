from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import MaterialCreate, MaterialResponse
from paperbrain.domain.materials import MaterialSpec

router = APIRouter(prefix="/v1/materials", tags=["materials"])


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
def create_material(
    body: MaterialCreate,
    container: Annotated[Container, Depends(get_container)],
) -> MaterialSpec:
    material = MaterialSpec(**body.model_dump())
    container.materials.save(material)
    return material


@router.get("", response_model=tuple[MaterialResponse, ...])
def list_materials(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[MaterialSpec, ...]:
    return container.materials.list_all()
