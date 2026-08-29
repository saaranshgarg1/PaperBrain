from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import NamedEntityCreate, NamedEntityResponse

router = APIRouter(prefix="/v1", tags=["reference-data"])


def _named_entities(directory: dict[str, object]) -> tuple[NamedEntityResponse, ...]:
    return tuple(
        sorted(
            (NamedEntityResponse(id=entity_id, name=name) for name, entity_id in directory.items()),
            key=lambda item: item.name.lower(),
        )
    )


def _get_or_create(directory: dict[str, object], name: str) -> NamedEntityResponse:
    existing = directory.get(name)
    if existing is not None:
        return NamedEntityResponse(id=existing, name=name)
    entity_id = uuid4()
    directory[name] = entity_id
    return NamedEntityResponse(id=entity_id, name=name)


@router.get("/locations", response_model=tuple[NamedEntityResponse, ...])
def list_locations(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[NamedEntityResponse, ...]:
    return _named_entities(container.locations)


@router.post(
    "/locations",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    body: NamedEntityCreate,
    container: Annotated[Container, Depends(get_container)],
) -> NamedEntityResponse:
    return _get_or_create(container.locations, body.name.strip())


@router.get("/customers", response_model=tuple[NamedEntityResponse, ...])
def list_customers(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[NamedEntityResponse, ...]:
    return _named_entities(container.customers)


@router.post(
    "/customers",
    response_model=NamedEntityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(
    body: NamedEntityCreate,
    container: Annotated[Container, Depends(get_container)],
) -> NamedEntityResponse:
    return _get_or_create(container.customers, body.name.strip())
