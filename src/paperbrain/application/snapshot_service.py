from __future__ import annotations

from datetime import UTC, datetime

from paperbrain.application.ports import (
    MachineRepository,
    MaterialRepository,
    OrderRepository,
    ReelRepository,
    ReelSegmentRepository,
)
from paperbrain.domain.enums import OrderStatus
from paperbrain.domain.policies import PolicyProfile
from paperbrain.domain.snapshots import PlanningSnapshot


class SnapshotService:
    def __init__(
        self,
        reels: ReelRepository,
        segments: ReelSegmentRepository,
        orders: OrderRepository,
        machines: MachineRepository,
        materials: MaterialRepository,
    ) -> None:
        self._reels = reels
        self._segments = segments
        self._orders = orders
        self._machines = machines
        self._materials = materials

    def create(
        self,
        policy: PolicyProfile,
        *,
        order_ids: frozenset[UUID] | None = None,
    ) -> PlanningSnapshot:
        reels = tuple(item for item in self._reels.list_all() if item.is_executable)
        reel_ids = {item.id for item in reels}
        segments = tuple(
            item
            for item in self._segments.list_all()
            if item.reel_id in reel_ids and item.inspection_verified
        )
        plannable = {
            item.id: item
            for item in self._orders.list_all()
            if item.status in {OrderStatus.CONFIRMED, OrderStatus.RELEASED, OrderStatus.RUNNING}
        }
        if order_ids is None:
            orders = tuple(plannable.values())
        else:
            orders = tuple(
                plannable[order_id] for order_id in plannable.keys() & order_ids
            )
        order_ids_selected = {item.id for item in orders}
        return PlanningSnapshot(
            created_at=datetime.now(UTC),
            orders=orders,
            order_lines=tuple(
                item for item in self._orders.list_lines() if item.order_id in order_ids_selected
            ),
            reels=reels,
            reel_segments=segments,
            machines=self._machines.list_all(),
            materials=self._materials.list_all(),
            substitutions=self._materials.list_substitutions(),
            policy=policy,
        )