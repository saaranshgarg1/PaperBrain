from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    QuarantineRequest,
    ReelCreate,
    ReelResponse,
    ReserveRequest,
    VerifyRequest,
)
from paperbrain.domain.reels import Reel

router = APIRouter(prefix="/v1/reels", tags=["reels"])


@router.post("", response_model=ReelResponse, status_code=status.HTTP_201_CREATED)
def create_reel(
    body: ReelCreate,
    container: Annotated[Container, Depends(get_container)],
) -> Reel:
    reel = Reel(**body.model_dump())
    return container.inventory_service.register_reel(reel, actor_id=None)


@router.get("", response_model=tuple[ReelResponse, ...])
def list_reels(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[Reel, ...]:
    return container.reels.list_all()


@router.get("/{reel_id}", response_model=ReelResponse)
def get_reel(
    reel_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> Reel:
    return container.reels.get(reel_id)


@router.post("/{reel_id}/verify", response_model=ReelResponse)
def verify_reel(
    reel_id: UUID,
    body: VerifyRequest,
    container: Annotated[Container, Depends(get_container)],
) -> Reel:
    return container.inventory_service.verify_reel(reel_id, actor_id=body.actor_id)


@router.post("/{reel_id}/reserve", response_model=ReelResponse)
def reserve_reel(
    reel_id: UUID,
    body: ReserveRequest,
    container: Annotated[Container, Depends(get_container)],
) -> Reel:
    return container.inventory_service.reserve(
        reel_id,
        body.reservation_id,
        actor_id=body.actor_id,
    )


@router.post("/{reel_id}/quarantine", response_model=ReelResponse)
def quarantine_reel(
    reel_id: UUID,
    body: QuarantineRequest,
    container: Annotated[Container, Depends(get_container)],
) -> Reel:
    return container.inventory_service.quarantine(
        reel_id,
        actor_id=body.actor_id,
        reason=body.reason,
    )


@router.post("/{reel_id}/release", response_model=ReelResponse)
def release_reel(
    reel_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> Reel:
    return container.inventory_service.release_from_hold(reel_id, actor_id=None)
