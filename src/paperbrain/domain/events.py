from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import UUID, uuid4

from paperbrain.domain.enums import EventType
from paperbrain.domain.errors import DomainError, DomainViolation


@dataclass(frozen=True, slots=True)
class DomainEvent:
    aggregate_id: UUID
    aggregate_type: str
    aggregate_version: int
    event_type: EventType
    payload: Mapping[str, Any]
    actor_id: UUID | None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.aggregate_version <= 0:
            raise DomainError(DomainViolation("INVALID_EVENT_VERSION", "Event version must be positive"))
        if self.occurred_at.tzinfo is None:
            raise DomainError(DomainViolation("NAIVE_TIMESTAMP", "Event timestamp must be timezone-aware"))