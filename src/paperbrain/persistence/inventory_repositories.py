from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from paperbrain.application.ports import EventStore, ReelRepository, ReelSegmentRepository
from paperbrain.domain.enums import EventType, QualityStatus, ReelState, VerificationState
from paperbrain.domain.errors import ConcurrencyError, NotFoundError
from paperbrain.domain.events import DomainEvent
from paperbrain.domain.reels import Reel, ReelSegment
from paperbrain.persistence.models import DomainEventRow, ReelRow, ReelSegmentRow


class SqlReelRepository(ReelRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, reel_id: UUID) -> Reel:
        row = self._session.get(ReelRow, reel_id)
        if row is None:
            raise NotFoundError(f"Reel {reel_id} was not found")
        return _reel_from_row(row)

    def get_by_code(self, reel_code: str) -> Reel:
        row = self._session.scalar(select(ReelRow).where(ReelRow.reel_code == reel_code))
        if row is None:
            raise NotFoundError(f"Reel code {reel_code!r} was not found")
        return _reel_from_row(row)

    def list_all(self) -> tuple[Reel, ...]:
        rows = self._session.scalars(select(ReelRow).order_by(ReelRow.reel_code)).all()
        return tuple(_reel_from_row(row) for row in rows)

    def save(self, reel: Reel, *, expected_version: int | None = None) -> None:
        values = _reel_values(reel)
        current = self._session.get(ReelRow, reel.id)
        if current is None:
            if expected_version is not None:
                raise ConcurrencyError("Cannot update a reel that does not exist")
            self._session.add(ReelRow(**values))
            return
        if expected_version is None:
            raise ConcurrencyError("Existing reel update requires an expected version")
        result = self._session.execute(
            update(ReelRow)
            .where(ReelRow.id == reel.id, ReelRow.version == expected_version)
            .values(**{key: value for key, value in values.items() if key != "id"})
        )
        if result.rowcount != 1:
            raise ConcurrencyError(
                f"Expected reel version {expected_version}; concurrent update detected"
            )
        self._session.expire(current)


class SqlReelSegmentRepository(ReelSegmentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> tuple[ReelSegment, ...]:
        rows = self._session.scalars(
            select(ReelSegmentRow).order_by(
                ReelSegmentRow.reel_id,
                ReelSegmentRow.start_length_mm,
            )
        ).all()
        return tuple(_segment_from_row(row) for row in rows)

    def list_for_reel(self, reel_id: UUID) -> tuple[ReelSegment, ...]:
        rows = self._session.scalars(
            select(ReelSegmentRow)
            .where(ReelSegmentRow.reel_id == reel_id)
            .order_by(ReelSegmentRow.start_length_mm)
        ).all()
        return tuple(_segment_from_row(row) for row in rows)

    def replace_for_reel(self, reel_id: UUID, segments: tuple[ReelSegment, ...]) -> None:
        if any(segment.reel_id != reel_id for segment in segments):
            raise ValueError("Every segment must belong to the requested reel")
        self._session.execute(delete(ReelSegmentRow).where(ReelSegmentRow.reel_id == reel_id))
        self._session.add_all(
            ReelSegmentRow(
                id=item.id,
                reel_id=item.reel_id,
                start_length_mm=item.start_length_mm,
                end_length_mm=item.end_length_mm,
                left_unusable_mm=item.left_unusable_mm,
                right_unusable_mm=item.right_unusable_mm,
                mandatory_left_trim_mm=item.mandatory_left_trim_mm,
                mandatory_right_trim_mm=item.mandatory_right_trim_mm,
                confidence=item.confidence,
                inspection_verified=item.inspection_verified,
            )
            for item in segments
        )


class SqlEventStore(EventStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: DomainEvent, *, expected_version: int) -> None:
        latest = self._session.scalar(
            select(DomainEventRow)
            .where(DomainEventRow.aggregate_id == event.aggregate_id)
            .order_by(DomainEventRow.aggregate_version.desc())
            .limit(1)
            .with_for_update()
        )
        actual_version = 0 if latest is None else latest.aggregate_version
        if actual_version != expected_version or event.aggregate_version != expected_version + 1:
            raise ConcurrencyError(
                f"Expected aggregate version {expected_version}, found {actual_version}"
            )
        self._session.add(
            DomainEventRow(
                id=event.id,
                aggregate_id=event.aggregate_id,
                aggregate_type=event.aggregate_type,
                aggregate_version=event.aggregate_version,
                event_type=event.event_type,
                payload=dict(event.payload),
                actor_id=event.actor_id,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
            )
        )

    def for_aggregate(self, aggregate_id: UUID) -> tuple[DomainEvent, ...]:
        rows = self._session.scalars(
            select(DomainEventRow)
            .where(DomainEventRow.aggregate_id == aggregate_id)
            .order_by(DomainEventRow.aggregate_version)
        ).all()
        return tuple(
            DomainEvent(
                id=row.id,
                aggregate_id=row.aggregate_id,
                aggregate_type=row.aggregate_type,
                aggregate_version=row.aggregate_version,
                event_type=EventType(row.event_type),
                payload=row.payload,
                actor_id=row.actor_id,
                occurred_at=row.occurred_at,
                correlation_id=row.correlation_id,
                causation_id=row.causation_id,
            )
            for row in rows
        )


def _reel_values(reel: Reel) -> dict[str, object]:
    return {
        "id": reel.id,
        "reel_code": reel.reel_code,
        "root_reel_id": reel.root_reel_id,
        "parent_reel_id": reel.parent_reel_id,
        "material_spec_id": reel.material_spec_id,
        "nominal_width_mm": reel.nominal_width_mm,
        "remaining_length_mm": reel.remaining_length_mm,
        "remaining_length_low_mm": reel.remaining_length_low_mm,
        "remaining_length_high_mm": reel.remaining_length_high_mm,
        "length_confidence": reel.length_confidence,
        "net_mass_kg": reel.net_mass_kg,
        "location_id": reel.location_id,
        "state": reel.state,
        "verification_state": reel.verification_state,
        "quality_status": reel.quality_status,
        "reservation_id": reel.reservation_id,
        "received_at": reel.received_at,
        "opened_at": reel.opened_at,
        "last_used_at": reel.last_used_at,
        "handling_count": reel.handling_count,
        "version": reel.version,
    }


def _reel_from_row(row: ReelRow) -> Reel:
    return Reel(
        id=row.id,
        reel_code=row.reel_code,
        root_reel_id=row.root_reel_id,
        parent_reel_id=row.parent_reel_id,
        material_spec_id=row.material_spec_id,
        nominal_width_mm=row.nominal_width_mm,
        remaining_length_mm=row.remaining_length_mm,
        remaining_length_low_mm=row.remaining_length_low_mm,
        remaining_length_high_mm=row.remaining_length_high_mm,
        length_confidence=row.length_confidence,
        net_mass_kg=row.net_mass_kg,
        location_id=row.location_id,
        state=ReelState(row.state),
        verification_state=VerificationState(row.verification_state),
        quality_status=QualityStatus(row.quality_status),
        reservation_id=row.reservation_id,
        received_at=row.received_at,
        opened_at=row.opened_at,
        last_used_at=row.last_used_at,
        handling_count=row.handling_count,
        version=row.version,
    )


def _segment_from_row(row: ReelSegmentRow) -> ReelSegment:
    return ReelSegment(
        id=row.id,
        reel_id=row.reel_id,
        start_length_mm=row.start_length_mm,
        end_length_mm=row.end_length_mm,
        left_unusable_mm=row.left_unusable_mm,
        right_unusable_mm=row.right_unusable_mm,
        mandatory_left_trim_mm=row.mandatory_left_trim_mm,
        mandatory_right_trim_mm=row.mandatory_right_trim_mm,
        confidence=row.confidence,
        inspection_verified=row.inspection_verified,
    )
