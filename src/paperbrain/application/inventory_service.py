from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from paperbrain.application.ports import EventStore, ReelRepository, ReelSegmentRepository
from paperbrain.domain.enums import EventType, ReelState, VerificationState
from paperbrain.domain.errors import DomainError, DomainViolation
from paperbrain.domain.events import DomainEvent
from paperbrain.domain.reels import Reel


class InventoryService:
    def __init__(
        self,
        reels: ReelRepository,
        segments: ReelSegmentRepository,
        events: EventStore,
    ) -> None:
        self._reels = reels
        self._segments = segments
        self._events = events

    def register_reel(self, reel: Reel, *, actor_id: UUID | None) -> Reel:
        if reel.version != 0:
            raise DomainError(DomainViolation("INVALID_INITIAL_VERSION", "New reel version must be zero"))
        if reel.remaining_length_mm <= 0:
            raise DomainError(DomainViolation("INVALID_LENGTH", "New reel must have positive length"))
        registered = replace(reel, version=1)
        self._reels.save(registered, expected_version=None)
        segment = registered.default_segment()
        self._segments.replace_for_reel(registered.id, (segment,))
        self._append(
            registered,
            EventType.REEL_RECEIVED,
            actor_id,
            {
                "reel_code": registered.reel_code,
                "material_spec_id": str(registered.material_spec_id),
                "nominal_width_mm": registered.nominal_width_mm,
                "remaining_length_mm": registered.remaining_length_mm,
                "location_id": str(registered.location_id),
            },
            expected_version=0,
            aggregate_version=1,
        )
        return registered

    def verify_reel(self, reel_id: UUID, *, actor_id: UUID | None) -> Reel:
        reel = self._reels.get(reel_id)
        if reel.state in {ReelState.MISSING, ReelState.SCRAPPED, ReelState.EXHAUSTED, ReelState.SPLIT}:
            raise DomainError(
                DomainViolation("INVALID_STATE_TRANSITION", "Terminal or missing reel cannot be verified")
            )
        updated = replace(
            reel,
            verification_state=VerificationState.VERIFIED,
            version=reel.version + 1,
        )
        self._reels.save(updated, expected_version=reel.version)
        self._append_state_event(updated, EventType.REEL_INSPECTED, actor_id, reel.version)
        return updated

    def reserve(self, reel_id: UUID, reservation_id: UUID, *, actor_id: UUID | None) -> Reel:
        reel = self._reels.get(reel_id)
        updated = reel.with_reservation(reservation_id)
        self._reels.save(updated, expected_version=reel.version)
        self._append_state_event(
            updated,
            EventType.REEL_RESERVED,
            actor_id,
            reel.version,
            {"reservation_id": str(reservation_id)},
        )
        return updated

    def release_reservation(self, reel_id: UUID, *, actor_id: UUID | None) -> Reel:
        reel = self._reels.get(reel_id)
        reservation = reel.reservation_id
        updated = reel.release_reservation()
        self._reels.save(updated, expected_version=reel.version)
        self._append_state_event(
            updated,
            EventType.RESERVATION_RELEASED,
            actor_id,
            reel.version,
            {"reservation_id": str(reservation) if reservation else None},
        )
        return updated

    def quarantine(self, reel_id: UUID, *, actor_id: UUID | None, reason: str) -> Reel:
        reel = self._reels.get(reel_id)
        updated = reel.quarantine()
        self._reels.save(updated, expected_version=reel.version)
        self._append_state_event(
            updated,
            EventType.REEL_QUARANTINED,
            actor_id,
            reel.version,
            {"reason": reason},
        )
        return updated

    def move(self, reel_id: UUID, location_id: UUID, *, actor_id: UUID | None) -> Reel:
        reel = self._reels.get(reel_id)
        updated = replace(
            reel,
            location_id=location_id,
            handling_count=reel.handling_count + 1,
            version=reel.version + 1,
        )
        self._reels.save(updated, expected_version=reel.version)
        self._append_state_event(
            updated,
            EventType.REEL_MOVED,
            actor_id,
            reel.version,
            {"location_id": str(location_id)},
        )
        return updated

    def split(
        self,
        parent_id: UUID,
        children: tuple[Reel, ...],
        *,
        waste_length_equivalent_mm: int,
        actor_id: UUID | None,
    ) -> tuple[Reel, ...]:
        parent = self._reels.get(parent_id)
        if parent.state not in {ReelState.OPENED, ReelState.RUNNING, ReelState.RESERVED}:
            raise DomainError(DomainViolation("INVALID_SPLIT_STATE", "Parent reel cannot be split"))
        if not children:
            raise DomainError(DomainViolation("EMPTY_SPLIT", "A split must create at least one child"))
        if waste_length_equivalent_mm < 0:
            raise DomainError(DomainViolation("INVALID_WASTE", "Waste cannot be negative"))
        for child in children:
            if child.version != 0:
                raise DomainError(DomainViolation("INVALID_INITIAL_VERSION", "New child version must be zero"))
            if child.parent_reel_id != parent.id or child.root_reel_id != parent.root_reel_id:
                raise DomainError(DomainViolation("INVALID_LINEAGE", "Child lineage does not match parent"))
            if child.material_spec_id != parent.material_spec_id:
                raise DomainError(DomainViolation("MATERIAL_INCOMPATIBLE", "Child material differs from parent"))
            if child.nominal_width_mm > parent.nominal_width_mm:
                raise DomainError(DomainViolation("INVALID_CHILD_WIDTH", "Child width exceeds parent width"))
        parent_area = parent.nominal_width_mm * parent.remaining_length_mm
        child_area = sum(child.nominal_width_mm * child.remaining_length_mm for child in children)
        waste_area = parent.nominal_width_mm * waste_length_equivalent_mm
        if child_area + waste_area > parent_area:
            raise DomainError(
                DomainViolation(
                    "PARENT_CHILD_BALANCE",
                    "Child and waste area exceed the remaining parent material",
                )
            )

        updated_parent = replace(
            parent,
            state=ReelState.SPLIT,
            reservation_id=None,
            remaining_length_mm=0,
            version=parent.version + 1,
        )
        self._reels.save(updated_parent, expected_version=parent.version)
        self._append_state_event(
            updated_parent,
            EventType.REEL_SPLIT,
            actor_id,
            parent.version,
            {
                "children": [str(child.id) for child in children],
                "waste_length_equivalent_mm": waste_length_equivalent_mm,
            },
        )
        self._segments.replace_for_reel(parent.id, ())
        registered_children: list[Reel] = []
        for child in children:
            registered_child = replace(child, version=1)
            self._reels.save(registered_child)
            self._segments.replace_for_reel(
                registered_child.id,
                (registered_child.default_segment(),),
            )
            self._append(
                registered_child,
                EventType.CHILD_REEL_CREATED,
                actor_id,
                {"parent_reel_id": str(parent.id), "root_reel_id": str(parent.root_reel_id)},
                expected_version=0,
                aggregate_version=1,
            )
            registered_children.append(registered_child)
        return tuple(registered_children)

    def _append_state_event(
        self,
        reel: Reel,
        event_type: EventType,
        actor_id: UUID | None,
        previous_version: int,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._append(
            reel,
            event_type,
            actor_id,
            {"state": reel.state, **(payload or {})},
            expected_version=previous_version,
            aggregate_version=previous_version + 1,
        )

    def _append(
        self,
        reel: Reel,
        event_type: EventType,
        actor_id: UUID | None,
        payload: dict[str, Any],
        *,
        expected_version: int,
        aggregate_version: int,
    ) -> None:
        event = DomainEvent(
            aggregate_id=reel.id,
            aggregate_type="reel",
            aggregate_version=aggregate_version,
            event_type=event_type,
            payload=payload,
            actor_id=actor_id,
            occurred_at=datetime.now(UTC),
            correlation_id=uuid4(),
        )
        self._events.append(event, expected_version=expected_version)