from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    MeasureReelRequest,
    QuarantineRequest,
    ReelCreate,
    ReelResponse,
    ReserveRequest,
    VerifyRequest,
)
from paperbrain.domain.reels import Reel

router = APIRouter(prefix="/v1/reels", tags=["reels"])


def _reel_response(container: Container, reel: Reel) -> ReelResponse:
    """Serialize a reel, joining edge-spoilage recorded on its live segment."""
    response = ReelResponse.model_validate(reel, from_attributes=True)
    segments = container.segments.list_for_reel(reel.id)
    if segments:
        response = response.model_copy(
            update={
                "left_unusable_mm": segments[0].left_unusable_mm,
                "right_unusable_mm": segments[0].right_unusable_mm,
            }
        )
    return response


@router.post("", response_model=ReelResponse, status_code=status.HTTP_201_CREATED)
def create_reel(
    body: ReelCreate,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    reel = Reel(**body.model_dump())
    return _reel_response(container, container.inventory_service.register_reel(reel, actor_id=None))


@router.get("", response_model=tuple[ReelResponse, ...])
def list_reels(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[ReelResponse, ...]:
    return tuple(_reel_response(container, reel) for reel in container.reels.list_all())


@router.get("/{reel_id}", response_model=ReelResponse)
def get_reel(
    reel_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    return _reel_response(container, container.reels.get(reel_id))


@router.post("/{reel_id}/verify", response_model=ReelResponse)
def verify_reel(
    reel_id: UUID,
    body: VerifyRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    return _reel_response(
        container, container.inventory_service.verify_reel(reel_id, actor_id=body.actor_id)
    )


@router.post("/{reel_id}/measure", response_model=ReelResponse)
def measure_reel(
    reel_id: UUID,
    body: MeasureReelRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    """Record a physical check: actual length left and any damage on the sides."""
    return _reel_response(
        container,
        container.inventory_service.measure_reel(
            reel_id,
            remaining_length_mm=body.remaining_length_mm,
            left_unusable_mm=body.left_unusable_mm,
            right_unusable_mm=body.right_unusable_mm,
            actor_id=None,
        ),
    )


@router.post("/{reel_id}/reserve", response_model=ReelResponse)
def reserve_reel(
    reel_id: UUID,
    body: ReserveRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    return _reel_response(
        container,
        container.inventory_service.reserve(
            reel_id,
            body.reservation_id,
            actor_id=body.actor_id,
        ),
    )


@router.post("/{reel_id}/quarantine", response_model=ReelResponse)
def quarantine_reel(
    reel_id: UUID,
    body: QuarantineRequest,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    return _reel_response(
        container,
        container.inventory_service.quarantine(
            reel_id,
            actor_id=body.actor_id,
            reason=body.reason,
        ),
    )


@router.post("/{reel_id}/release", response_model=ReelResponse)
def release_reel(
    reel_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> ReelResponse:
    return _reel_response(
        container, container.inventory_service.release_from_hold(reel_id, actor_id=None)
    )
