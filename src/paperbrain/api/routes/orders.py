from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.api.schemas import OrderCreate, OrderLineResponse, OrderResponse
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
