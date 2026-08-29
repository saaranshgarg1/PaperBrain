from __future__ import annotations

from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import (
    CancelOrderResponse,
    CompleteOrderRequest,
    OrderCreate,
    OrderLineResponse,
    OrderResponse,
)
from paperbrain.domain.enums import OrderStatus
from paperbrain.domain.errors import DomainError, DomainViolation
from paperbrain.domain.orders import CustomerOrder, OrderLine

router = APIRouter(prefix="/v1/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    body: OrderCreate,
    container: Annotated[Container, Depends(get_container)],
) -> OrderResponse:
    order_data = body.model_dump(exclude={"lines"})
    order = CustomerOrder(**order_data)
    lines = tuple(OrderLine(order_id=order.id, **line.model_dump()) for line in body.lines)
    container.orders.save(order, lines)
    return _response(order, lines)


@router.get("", response_model=tuple[OrderResponse, ...])
def list_orders(
    container: Annotated[Container, Depends(get_container)],
) -> tuple[OrderResponse, ...]:
    lines_by_order: dict[object, list[OrderLine]] = {}
    for line in container.orders.list_lines():
        lines_by_order.setdefault(line.order_id, []).append(line)
    return tuple(
        _response(order, tuple(lines_by_order.get(order.id, ())))
        for order in container.orders.list_all()
    )


@router.post("/{order_id}/cancel", response_model=CancelOrderResponse)
def cancel_order(
    order_id: UUID,
    container: Annotated[Container, Depends(get_container)],
) -> CancelOrderResponse:
    order = container.orders.get(order_id)
    if order.status == OrderStatus.COMPLETE:
        raise DomainError(
            DomainViolation("ORDER_ALREADY_COMPLETE", "A completed order cannot be cancelled")
        )
    if order.status == OrderStatus.CANCELLED:
        return CancelOrderResponse(id=order.id, external_id=order.external_id, status=order.status)
    updated = replace(order, status=OrderStatus.CANCELLED, version=order.version + 1)
    lines = tuple(
        line for line in container.orders.list_lines() if line.order_id == order.id
    )
    container.orders.save(updated, lines)
    return CancelOrderResponse(id=updated.id, external_id=updated.external_id, status=updated.status)


@router.post("/{order_id}/complete", response_model=CancelOrderResponse)
def complete_order(
    order_id: UUID,
    body: CompleteOrderRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CancelOrderResponse:
    """Mark an order as fulfilled by hand (e.g. produced outside PaperBrain)."""
    order = container.orders.get(order_id)
    if order.status == OrderStatus.CANCELLED:
        raise DomainError(
            DomainViolation("ORDER_CANCELLED", "A cancelled order cannot be completed")
        )
    if order.status == OrderStatus.COMPLETE:
        return CancelOrderResponse(id=order.id, external_id=order.external_id, status=order.status)
    updated = replace(order, status=OrderStatus.COMPLETE, version=order.version + 1)
    lines = tuple(
        line for line in container.orders.list_lines() if line.order_id == order.id
    )
    container.orders.save(updated, lines)
    return CancelOrderResponse(id=updated.id, external_id=updated.external_id, status=updated.status)


def _response(order: CustomerOrder, lines: tuple[OrderLine, ...]) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        external_id=order.external_id,
        received_at=order.received_at,
        promised_at=order.promised_at,
        status=order.status,
        priority=order.priority,
        service_class=order.service_class,
        version=order.version,
        lines=tuple(OrderLineResponse.model_validate(line) for line in lines),
    )
