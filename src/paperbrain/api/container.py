from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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
from paperbrain.optimization.preprocessing import PreparedProblem
from paperbrain.optimization.service import PlanningService
from paperbrain.optimization.solvers.cpsat import CpSatPlanner
from paperbrain.persistence.file_store import (
    FileStatePersistence,
    capture_state,
    restore_state,
)


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
    locations: dict[str, UUID] = field(default_factory=dict)
    customers: dict[str, UUID] = field(default_factory=dict)
    plan_reports: dict[UUID, dict] = field(default_factory=dict)
    executed_plans: dict[UUID, datetime] = field(default_factory=dict)
    persistence: FileStatePersistence | None = None

    def persist(self) -> None:
        if self.persistence is None:
            return
        state = capture_state(
            self.reels,
            self.segments,
            self.orders,
            self.machines,
            self.materials,
            self.events,
            self.plans,
            locations=self.locations,
            customers=self.customers,
            plan_reports=self.plan_reports,
            executed_plans=self.executed_plans,
        )
        self.persistence.save(state)


def build_container(
    *,
    state_path: str | Path | None = None,
    seed_demo: bool = False,
) -> Container:
    reels = InMemoryReelRepository()
    segments = InMemoryReelSegmentRepository()
    orders = InMemoryOrderRepository()
    machines = InMemoryMachineRepository()
    materials = InMemoryMaterialRepository()
    events = InMemoryEventStore()
    plans = InMemoryPlanRepository()

    persistence: FileStatePersistence | None = None
    if state_path:
        persistence = FileStatePersistence(Path(state_path))

    container = Container(
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
        persistence=persistence,
    )

    if persistence is not None:
        state = persistence.load()
        if state is not None:
            locations, customers, plan_reports, executed_plans = restore_state(
                state, reels, segments, orders, machines, materials, events, plans
            )
            container.locations = locations
            container.customers = customers
            container.plan_reports = plan_reports
            container.executed_plans = executed_plans

    if seed_demo and not reels.list_all():
        from paperbrain.demo.bootstrap import bootstrap_demo

        bootstrap_demo(container)
        container.persist()

    return container
