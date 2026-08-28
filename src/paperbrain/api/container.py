from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from paperbrain.application.in_memory import (
    InMemoryEventStore,
    InMemoryMachineRepository,
    InMemoryMaterialRepository,
    InMemoryOrderRepository,
    InMemoryPlanRepository,
    InMemoryReelRepository,
    InMemoryReelSegmentRepository,
)
from paperbrain.application.inventory_service import InventoryService
from paperbrain.application.snapshot_service import SnapshotService
from paperbrain.optimization.service import PlanningService
from paperbrain.optimization.preprocessing import PreparedProblem
from paperbrain.optimization.solvers.cpsat import CpSatPlanner


@dataclass(slots=True)
class Container:
    reels: InMemoryReelRepository
    segments: InMemoryReelSegmentRepository
    orders: InMemoryOrderRepository
    machines: InMemoryMachineRepository
    materials: InMemoryMaterialRepository
    events: InMemoryEventStore
    plans: InMemoryPlanRepository
    inventory_service: InventoryService
    snapshot_service: SnapshotService
    planning_service: PlanningService
    planning_contexts: dict[UUID, PreparedProblem]


def build_container() -> Container:
    reels = InMemoryReelRepository()
    segments = InMemoryReelSegmentRepository()
    orders = InMemoryOrderRepository()
    machines = InMemoryMachineRepository()
    materials = InMemoryMaterialRepository()
    events = InMemoryEventStore()
    plans = InMemoryPlanRepository()
    return Container(
        reels=reels,
        segments=segments,
        orders=orders,
        machines=machines,
        materials=materials,
        events=events,
        plans=plans,
        inventory_service=InventoryService(reels, segments, events),
        snapshot_service=SnapshotService(reels, segments, orders, machines, materials),
        planning_service=PlanningService(CpSatPlanner()),
        planning_contexts={},
    )