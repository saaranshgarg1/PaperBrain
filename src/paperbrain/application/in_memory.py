from __future__ import annotations

from threading import RLock
from uuid import UUID

from paperbrain.application.ports import (
    EventStore,
    MachineRepository,
    MaterialRepository,
    OrderRepository,
    PlanRepository,
    ReelRepository,
    ReelSegmentRepository,
)
from paperbrain.domain.errors import ConcurrencyError, NotFoundError
from paperbrain.domain.events import DomainEvent
from paperbrain.domain.machines import Machine
from paperbrain.domain.materials import MaterialSpec, MaterialSubstitution
from paperbrain.domain.orders import CustomerOrder, OrderLine
from paperbrain.domain.plans import Plan
from paperbrain.domain.reels import Reel, ReelSegment


class InMemoryReelRepository(ReelRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Reel] = {}
        self._codes: dict[str, UUID] = {}
        self._lock = RLock()

    def get(self, reel_id: UUID) -> Reel:
        try:
            return self._items[reel_id]
        except KeyError as exc:
            raise NotFoundError(f"Reel {reel_id} was not found") from exc

    def get_by_code(self, reel_code: str) -> Reel:
        try:
            return self.get(self._codes[reel_code])
        except KeyError as exc:
            raise NotFoundError(f"Reel code {reel_code!r} was not found") from exc

    def list_all(self) -> tuple[Reel, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: item.reel_code))

    def save(self, reel: Reel, *, expected_version: int | None = None) -> None:
        with self._lock:
            current = self._items.get(reel.id)
            if expected_version is not None:
                actual = -1 if current is None else current.version
                if actual != expected_version:
                    raise ConcurrencyError(
                        f"Expected reel version {expected_version}, found {actual}"
                    )
            owner = self._codes.get(reel.reel_code)
            if owner is not None and owner != reel.id:
                raise ConcurrencyError(f"Reel code {reel.reel_code!r} is already active")
            self._items[reel.id] = reel
            self._codes[reel.reel_code] = reel.id


class InMemoryReelSegmentRepository(ReelSegmentRepository):
    def __init__(self) -> None:
        self._by_reel: dict[UUID, tuple[ReelSegment, ...]] = {}

    def list_all(self) -> tuple[ReelSegment, ...]:
        return tuple(segment for group in self._by_reel.values() for segment in group)

    def list_for_reel(self, reel_id: UUID) -> tuple[ReelSegment, ...]:
        return self._by_reel.get(reel_id, ())

    def replace_for_reel(self, reel_id: UUID, segments: tuple[ReelSegment, ...]) -> None:
        if any(segment.reel_id != reel_id for segment in segments):
            raise ValueError("Every segment must belong to the requested reel")
        self._by_reel[reel_id] = tuple(sorted(segments, key=lambda item: item.start_length_mm))


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self._orders: dict[UUID, CustomerOrder] = {}
        self._lines: dict[UUID, OrderLine] = {}

    def get(self, order_id: UUID) -> CustomerOrder:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise NotFoundError(f"Order {order_id} was not found") from exc

    def list_all(self) -> tuple[CustomerOrder, ...]:
        return tuple(sorted(self._orders.values(), key=lambda item: item.promised_at))

    def list_lines(self) -> tuple[OrderLine, ...]:
        return tuple(sorted(self._lines.values(), key=lambda item: (item.due_at, str(item.id))))

    def save(self, order: CustomerOrder, lines: tuple[OrderLine, ...]) -> None:
        if any(line.order_id != order.id for line in lines):
            raise ValueError("Every order line must belong to the order")
        self._orders[order.id] = order
        for line in lines:
            self._lines[line.id] = line


class InMemoryMachineRepository(MachineRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Machine] = {}

    def list_all(self) -> tuple[Machine, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: item.code))

    def save(self, machine: Machine) -> None:
        self._items[machine.id] = machine


class InMemoryMaterialRepository(MaterialRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, MaterialSpec] = {}
        self._substitutions: dict[UUID, MaterialSubstitution] = {}

    def list_all(self) -> tuple[MaterialSpec, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: (item.family, item.grade)))

    def list_substitutions(self) -> tuple[MaterialSubstitution, ...]:
        return tuple(self._substitutions.values())

    def save(self, material: MaterialSpec) -> None:
        self._items[material.id] = material

    def save_substitution(self, substitution: MaterialSubstitution) -> None:
        self._substitutions[substitution.id] = substitution


class InMemoryEventStore(EventStore):
    def __init__(self) -> None:
        self._events: dict[UUID, list[DomainEvent]] = {}
        self._lock = RLock()

    def append(self, event: DomainEvent, *, expected_version: int) -> None:
        with self._lock:
            events = self._events.setdefault(event.aggregate_id, [])
            if len(events) != expected_version:
                raise ConcurrencyError(
                    f"Expected aggregate version {expected_version}, found {len(events)}"
                )
            if event.aggregate_version != expected_version + 1:
                raise ConcurrencyError("Event version does not follow expected version")
            events.append(event)

    def for_aggregate(self, aggregate_id: UUID) -> tuple[DomainEvent, ...]:
        return tuple(self._events.get(aggregate_id, ()))

    def list_all(self) -> tuple[DomainEvent, ...]:
        with self._lock:
            return tuple(
                event for events in self._events.values() for event in events
            )

    def restore(self, events: tuple[DomainEvent, ...]) -> None:
        """Bulk-load a previously persisted event stream (no version checks)."""
        with self._lock:
            self._events = {}
            for event in events:
                self._events.setdefault(event.aggregate_id, []).append(event)


class InMemoryPlanRepository(PlanRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Plan] = {}

    def get(self, plan_id: UUID) -> Plan:
        try:
            return self._items[plan_id]
        except KeyError as exc:
            raise NotFoundError(f"Plan {plan_id} was not found") from exc

    def save(self, plan: Plan) -> None:
        self._items[plan.id] = plan

    def list_all(self) -> tuple[Plan, ...]:
        return tuple(self._items.values())
