from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from paperbrain.domain.machines import Machine
from paperbrain.domain.materials import MaterialSpec, MaterialSubstitution
from paperbrain.domain.orders import CustomerOrder, OrderLine
from paperbrain.domain.policies import PolicyProfile
from paperbrain.domain.reels import Reel, ReelSegment


@dataclass(frozen=True, slots=True)
class PlanningSnapshot:
    created_at: datetime
    orders: tuple[CustomerOrder, ...]
    order_lines: tuple[OrderLine, ...]
    reels: tuple[Reel, ...]
    reel_segments: tuple[ReelSegment, ...]
    machines: tuple[Machine, ...]
    materials: tuple[MaterialSpec, ...]
    substitutions: tuple[MaterialSubstitution, ...]
    policy: PolicyProfile
    id: UUID = field(default_factory=uuid4)

    @property
    def checksum(self) -> str:
        payload = {
            "created_at": self.created_at,
            "policy": self.policy,
            "orders": sorted(self.orders, key=lambda item: str(item.id)),
            "order_lines": sorted(self.order_lines, key=lambda item: str(item.id)),
            "reels": sorted(self.reels, key=lambda item: str(item.id)),
            "reel_segments": sorted(self.reel_segments, key=lambda item: str(item.id)),
            "machines": sorted(self.machines, key=lambda item: str(item.id)),
            "materials": sorted(self.materials, key=lambda item: str(item.id)),
            "substitutions": sorted(self.substitutions, key=lambda item: str(item.id)),
        }
        encoded = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    def reel_by_id(self) -> dict[UUID, Reel]:
        return {item.id: item for item in self.reels}

    def segment_by_id(self) -> dict[UUID, ReelSegment]:
        return {item.id: item for item in self.reel_segments}

    def line_by_id(self) -> dict[UUID, OrderLine]:
        return {item.id: item for item in self.order_lines}

    def machine_by_id(self) -> dict[UUID, Machine]:
        return {item.id: item for item in self.machines}

    def material_by_id(self) -> dict[UUID, MaterialSpec]:
        return {item.id: item for item in self.materials}


def _canonical(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(item) for item in value), key=str)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value