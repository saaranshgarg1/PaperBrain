from __future__ import annotations

import dataclasses
import enum
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
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
from paperbrain.domain.events import DomainEvent

STATE_VERSION = 1


def to_jsonable(value: Any) -> Any:
    # Enum must be checked before str/int: StrEnum and IntEnum subclass them.
    if isinstance(value, enum.Enum):
        return {"__enum__": f"{type(value).__name__}.{value.name}"}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, UUID):
        return {"__uuid__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, (frozenset, set)):
        return {"__set__": [to_jsonable(item) for item in sorted(value, key=str)]}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "__dataclass__": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {name: to_jsonable(item) for name, item in _fields_of(value).items()},
        }
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    raise TypeError(f"Cannot serialize value of type {type(value)!r}")


def _fields_of(instance: Any) -> dict[str, Any]:
    return {field.name: getattr(instance, field.name) for field in dataclasses.fields(instance)}


def _import_enum(module_name: str, name: str) -> type[enum.Enum] | None:
    import importlib

    try:
        module = importlib.import_module(module_name)
        return getattr(module, name)
    except (ImportError, AttributeError):
        return None


_ENUM_REGISTRY: dict[str, type[enum.Enum]] = {
    f"{cls.__name__}": cls
    for cls in (
        _import_enum("paperbrain.domain.enums", name)
        for name in (
            "VerificationState",
            "ReelState",
            "QualityStatus",
            "OrderStatus",
            "GrainRequirement",
            "EdgeLaneRestriction",
            "PlanningRunStatus",
            "MeasurementMethod",
            "PolicyName",
            "EventType",
        )
    )
    if cls is not None
}

_DATACLASS_REGISTRY: dict[str, type] = {}


def _dataclass_type(path: str) -> type:
    if path not in _DATACLASS_REGISTRY:
        module_name, _, class_name = path.rpartition(".")
        import importlib

        module = importlib.import_module(module_name)
        _DATACLASS_REGISTRY[path] = getattr(module, class_name)
    return _DATACLASS_REGISTRY[path]


def from_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        if "__decimal__" in value:
            return Decimal(value["__decimal__"])
        if "__uuid__" in value:
            return UUID(value["__uuid__"])
        if "__datetime__" in value:
            return datetime.fromisoformat(value["__datetime__"])
        if "__enum__" in value:
            enum_name, _, member_name = value["__enum__"].partition(".")
            return _ENUM_REGISTRY[enum_name][member_name]
        if "__set__" in value:
            return frozenset(from_jsonable(item) for item in value["__set__"])
        if "__dataclass__" in value:
            cls = _dataclass_type(value["__dataclass__"])
            kwargs = {
                name: from_jsonable(item) for name, item in value["fields"].items()
            }
            return cls(**kwargs)
        return {key: from_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_jsonable(item) for item in value]
    return value


class FileStatePersistence:
    """Snapshot persistence of the in-memory repositories to one JSON file.

    The whole container state is written atomically after every mutating
    request, so a restart continues exactly where the previous session left
    off without requiring PostgreSQL.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"state_version": STATE_VERSION, "state": to_jsonable(state)}
        tmp_path.write_text(_dumps(payload), encoding="utf-8")
        os.replace(tmp_path, self.path)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        payload = _loads(self.path.read_text(encoding="utf-8"))
        return from_jsonable(payload["state"])


def _dumps(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=1)


def _loads(text: str) -> Any:
    import json

    return json.loads(text)


def capture_state(
    reels: InMemoryReelRepository,
    segments: InMemoryReelSegmentRepository,
    orders: InMemoryOrderRepository,
    machines: InMemoryMachineRepository,
    materials: InMemoryMaterialRepository,
    events: InMemoryEventStore,
    plans: InMemoryPlanRepository,
    *,
    locations: dict[str, UUID],
    customers: dict[str, UUID],
    plan_reports: dict[UUID, dict],
) -> dict[str, Any]:
    return {
        "reels": reels.list_all(),
        "reel_segments": segments.list_all(),
        "orders": orders.list_all(),
        "order_lines": orders.list_lines(),
        "machines": machines.list_all(),
        "materials": materials.list_all(),
        "substitutions": materials.list_substitutions(),
        "events": events.list_all(),
        "plans": plans.list_all(),
        "locations": dict(locations),
        "customers": dict(customers),
        "plan_reports": {
            str(plan_id): report for plan_id, report in plan_reports.items()
        },
    }


def restore_state(
    state: dict[str, Any],
    reels: InMemoryReelRepository,
    segments: InMemoryReelSegmentRepository,
    orders: InMemoryOrderRepository,
    machines: InMemoryMachineRepository,
    materials: InMemoryMaterialRepository,
    events: InMemoryEventStore,
    plans: InMemoryPlanRepository,
) -> tuple[dict[str, UUID], dict[str, UUID], dict[UUID, dict]]:
    for reel in state["reels"]:
        reels.save(reel)
    for segment in state["reel_segments"]:
        by_reel: list = list(segments.list_for_reel(segment.reel_id))
        by_reel.append(segment)
        segments.replace_for_reel(segment.reel_id, tuple(by_reel))
    for order in state["orders"]:
        lines = tuple(
            line for line in state["order_lines"] if line.order_id == order.id
        )
        orders.save(order, lines)
    for machine in state["machines"]:
        machines.save(machine)
    for material in state["materials"]:
        materials.save(material)
    for substitution in state.get("substitutions", ()):
        materials.save_substitution(substitution)
    events.restore(state["events"])
    for plan in state["plans"]:
        plans.save(plan)
    locations: dict[str, UUID] = {
        name: UUID(str(value)) for name, value in state.get("locations", {}).items()
    }
    customers: dict[str, UUID] = {
        name: UUID(str(value)) for name, value in state.get("customers", {}).items()
    }
    plan_reports: dict[UUID, dict] = {
        UUID(str(plan_id)): report
        for plan_id, report in state.get("plan_reports", {}).items()
    }
    return locations, customers, plan_reports
