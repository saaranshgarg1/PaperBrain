from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MaterialSpecRow(Base):
    __tablename__ = "material_spec"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    family: Mapped[str] = mapped_column(String(80), index=True)
    grade: Mapped[str] = mapped_column(String(120), index=True)
    compatibility_group_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    gsm_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    gsm_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    gsm_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    supplier_id: Mapped[UUID | None] = mapped_column(Uuid)
    supplier_grade: Mapped[str | None] = mapped_column(String(120))
    finish: Mapped[str | None] = mapped_column(String(80))
    colour: Mapped[str | None] = mapped_column(String(80))
    coating: Mapped[str | None] = mapped_column(String(80))
    grain_rule: Mapped[str] = mapped_column(String(40), default="unrestricted")
    quality_class: Mapped[str] = mapped_column(String(40), default="released")
    cost_minor_per_kg: Mapped[int] = mapped_column(Integer, default=0)
    scrap_credit_minor_per_kg: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaterialSubstitutionRow(Base):
    __tablename__ = "material_substitution"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    requested_material_id: Mapped[UUID] = mapped_column(ForeignKey("material_spec.id"), index=True)
    substitute_material_id: Mapped[UUID] = mapped_column(ForeignKey("material_spec.id"), index=True)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID] = mapped_column(Uuid)


class ReelRow(Base):
    __tablename__ = "reel"
    __table_args__ = (
        Index("ix_reel_available", "state", "verification_state", "quality_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reel_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    root_reel_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    parent_reel_id: Mapped[UUID | None] = mapped_column(ForeignKey("reel.id"), index=True)
    material_spec_id: Mapped[UUID] = mapped_column(ForeignKey("material_spec.id"), index=True)
    nominal_width_mm: Mapped[int] = mapped_column(Integer)
    remaining_length_mm: Mapped[int] = mapped_column(BigInteger)
    remaining_length_low_mm: Mapped[int | None] = mapped_column(BigInteger)
    remaining_length_high_mm: Mapped[int | None] = mapped_column(BigInteger)
    length_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("0"))
    net_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    location_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    verification_state: Mapped[str] = mapped_column(String(40), index=True)
    quality_status: Mapped[str] = mapped_column(String(40), index=True)
    reservation_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handling_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class ReelSegmentRow(Base):
    __tablename__ = "reel_segment"
    __table_args__ = (
        UniqueConstraint("reel_id", "start_length_mm", "end_length_mm"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reel_id: Mapped[UUID] = mapped_column(ForeignKey("reel.id"), index=True)
    start_length_mm: Mapped[int] = mapped_column(BigInteger)
    end_length_mm: Mapped[int] = mapped_column(BigInteger)
    left_unusable_mm: Mapped[int] = mapped_column(Integer, default=0)
    right_unusable_mm: Mapped[int] = mapped_column(Integer, default=0)
    mandatory_left_trim_mm: Mapped[int] = mapped_column(Integer, default=0)
    mandatory_right_trim_mm: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("1"))
    inspection_verified: Mapped[bool] = mapped_column(Boolean, default=True)


class ReelMeasurementRow(Base):
    __tablename__ = "reel_measurement"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reel_id: Mapped[UUID] = mapped_column(ForeignKey("reel.id"), index=True)
    measurement_type: Mapped[str] = mapped_column(String(80))
    value: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    canonical_unit: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(40))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observed_by: Mapped[UUID | None] = mapped_column(Uuid)
    uncertainty: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    source_reference: Mapped[str | None] = mapped_column(String(500))
    original_value: Mapped[str | None] = mapped_column(Text)
    original_unit: Mapped[str | None] = mapped_column(String(40))
    verification_state: Mapped[str] = mapped_column(String(40))


class CustomerOrderRow(Base):
    __tablename__ = "customer_order"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    external_id: Mapped[str] = mapped_column(String(160), index=True)
    contract_id: Mapped[UUID | None] = mapped_column(Uuid)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    promised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    service_class: Mapped[str] = mapped_column(String(80), default="normal")
    source_reference: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)


class OrderLineRow(Base):
    __tablename__ = "order_line"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("customer_order.id"), index=True)
    sheet_width_mm: Mapped[int] = mapped_column(Integer)
    sheet_length_mm: Mapped[int] = mapped_column(Integer)
    quantity_required: Mapped[int] = mapped_column(Integer)
    quantity_min: Mapped[int] = mapped_column(Integer)
    quantity_max: Mapped[int] = mapped_column(Integer)
    pack_size: Mapped[int | None] = mapped_column(Integer)
    material_spec_id: Mapped[UUID] = mapped_column(ForeignKey("material_spec.id"), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    earliest_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotation_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    grain_requirement: Mapped[str] = mapped_column(String(40))
    edge_lane_restriction: Mapped[str] = mapped_column(String(40))
    split_across_reels_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    split_across_days_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    early_production_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    max_early_days: Mapped[int | None] = mapped_column(Integer)
    machine_allowlist: Mapped[list[str]] = mapped_column(JSON, default=list)
    machine_denylist: Mapped[list[str]] = mapped_column(JSON, default=list)
    recurrence_family_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    quality_class: Mapped[str] = mapped_column(String(40), default="released")
    version: Mapped[int] = mapped_column(Integer, default=1)


class MachineRow(Base):
    __tablename__ = "machine"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    min_web_width_mm: Mapped[int] = mapped_column(Integer)
    max_web_width_mm: Mapped[int] = mapped_column(Integer)
    min_crosscut_length_mm: Mapped[int] = mapped_column(Integer)
    max_crosscut_length_mm: Mapped[int] = mapped_column(Integer)
    min_lane_width_mm: Mapped[int] = mapped_column(Integer)
    max_lanes: Mapped[int] = mapped_column(Integer)
    inter_lane_kerf_mm: Mapped[int] = mapped_column(Integer, default=0)
    min_left_trim_mm: Mapped[int] = mapped_column(Integer, default=0)
    min_right_trim_mm: Mapped[int] = mapped_column(Integer, default=0)
    setup_loss_mm: Mapped[int] = mapped_column(Integer, default=0)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON)
    material_compatibility_groups: Mapped[list[str]] = mapped_column(JSON, default=list)


class DomainEventRow(Base):
    __tablename__ = "domain_event"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "aggregate_version", name="uq_event_aggregate_version"),
        Index("ix_event_aggregate", "aggregate_id", "aggregate_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid)
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    correlation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(Uuid)


class PlanningSnapshotRow(Base):
    __tablename__ = "planning_snapshot"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    policy_name: Mapped[str] = mapped_column(String(80))
    policy_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class PlanRow(Base):
    __tablename__ = "plan"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("planning_snapshot.id"), index=True)
    policy_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), index=True)
    objective: Mapped[dict[str, Any]] = mapped_column(JSON)
    solver: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_confirmations: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanRunRow(Base):
    __tablename__ = "plan_run"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plan.id"), index=True)
    reel_id: Mapped[UUID] = mapped_column(ForeignKey("reel.id"), index=True)
    reel_segment_id: Mapped[UUID] = mapped_column(ForeignKey("reel_segment.id"))
    machine_id: Mapped[UUID] = mapped_column(ForeignKey("machine.id"), index=True)
    pattern_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    crosscut_count: Mapped[int] = mapped_column(Integer)
    consumed_length_mm: Mapped[int] = mapped_column(BigInteger)
    outputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    sequence: Mapped[int] = mapped_column(Integer)


class OutboxRow(Base):
    __tablename__ = "outbox"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    topic: Mapped[str] = mapped_column(String(160), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class RawImportRow(Base):
    __tablename__ = "raw_import"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    filename: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    import_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[UUID | None] = mapped_column(Uuid)


class RawImportRecordRow(Base):
    __tablename__ = "raw_import_record"
    __table_args__ = (UniqueConstraint("import_id", "row_number"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(ForeignKey("raw_import.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    raw_values: Mapped[dict[str, Any]] = mapped_column(JSON)
    parsed_values: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    verification_state: Mapped[str] = mapped_column(String(40), default="provisional")
