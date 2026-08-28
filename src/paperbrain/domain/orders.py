from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from paperbrain.domain.enums import EdgeLaneRestriction, GrainRequirement, OrderStatus
from paperbrain.domain.errors import DomainError, DomainViolation


@dataclass(frozen=True, slots=True)
class OrderLine:
    order_id: UUID
    sheet_width_mm: int
    sheet_length_mm: int
    quantity_required: int
    quantity_min: int
    quantity_max: int
    material_spec_id: UUID
    due_at: datetime
    earliest_start_at: datetime
    rotation_allowed: bool = False
    grain_requirement: GrainRequirement = GrainRequirement.UNRESTRICTED
    edge_lane_restriction: EdgeLaneRestriction = EdgeLaneRestriction.NONE
    pack_size: int | None = None
    split_across_reels_allowed: bool = True
    split_across_days_allowed: bool = True
    early_production_allowed: bool = False
    max_early_days: int | None = None
    machine_allowlist: frozenset[UUID] = frozenset()
    machine_denylist: frozenset[UUID] = frozenset()
    recurrence_family_id: UUID | None = None
    quality_class: str = "released"
    version: int = 1
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.sheet_width_mm <= 0 or self.sheet_length_mm <= 0:
            raise DomainError(DomainViolation("INVALID_SHEET_DIMENSION", "Sheet dimensions must be positive"))
        if self.quantity_required <= 0:
            raise DomainError(DomainViolation("INVALID_QUANTITY", "Required quantity must be positive"))
        if not (0 <= self.quantity_min <= self.quantity_required <= self.quantity_max):
            raise DomainError(DomainViolation("INVALID_QUANTITY_RANGE", "Invalid quantity bounds"))
        if self.earliest_start_at.tzinfo is None or self.due_at.tzinfo is None:
            raise DomainError(DomainViolation("NAIVE_TIMESTAMP", "Order timestamps must be timezone-aware"))
        if self.due_at < self.earliest_start_at:
            raise DomainError(DomainViolation("INVALID_DUE_DATE", "Due date precedes earliest start"))
        if self.pack_size is not None and self.pack_size <= 0:
            raise DomainError(DomainViolation("INVALID_PACK_SIZE", "Pack size must be positive"))
        if self.early_production_allowed and self.max_early_days is None:
            raise DomainError(
                DomainViolation("MISSING_EARLY_LIMIT", "Early-production limit is required")
            )

    def machine_allowed(self, machine_id: UUID) -> bool:
        if machine_id in self.machine_denylist:
            return False
        return not self.machine_allowlist or machine_id in self.machine_allowlist


@dataclass(frozen=True, slots=True)
class CustomerOrder:
    customer_id: UUID
    external_id: str
    received_at: datetime
    promised_at: datetime
    status: OrderStatus = OrderStatus.DRAFT
    priority: int = 100
    service_class: str = "normal"
    contract_id: UUID | None = None
    source_reference: str | None = None
    version: int = 1
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise DomainError(DomainViolation("INVALID_ORDER_ID", "External order ID is required"))
        if self.received_at.tzinfo is None or self.promised_at.tzinfo is None:
            raise DomainError(DomainViolation("NAIVE_TIMESTAMP", "Order timestamps must be timezone-aware"))
        if self.priority < 0:
            raise DomainError(DomainViolation("INVALID_PRIORITY", "Priority cannot be negative"))