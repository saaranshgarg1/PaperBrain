from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paperbrain.domain.enums import (
    EdgeLaneRestriction,
    GrainRequirement,
    OrderStatus,
    PolicyName,
    QualityStatus,
    ReelState,
    VerificationState,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class MaterialCreate(ApiModel):
    family: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    compatibility_group_id: UUID
    gsm_value: Decimal | None = Field(default=None, gt=0)
    gsm_min: Decimal | None = Field(default=None, gt=0)
    gsm_max: Decimal | None = Field(default=None, gt=0)
    supplier_id: UUID | None = None
    supplier_grade: str | None = None
    finish: str | None = None
    colour: str | None = None
    coating: str | None = None
    cost_minor_per_kg: int = Field(default=0, ge=0)
    scrap_credit_minor_per_kg: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_gsm(self) -> MaterialCreate:
        if self.gsm_value is None and (self.gsm_min is None or self.gsm_max is None):
            raise ValueError("Exact GSM or a complete GSM range is required")
        return self


class MaterialResponse(MaterialCreate):
    id: UUID


class ReelCreate(ApiModel):
    reel_code: str = Field(min_length=1)
    material_spec_id: UUID
    nominal_width_mm: int = Field(gt=0)
    remaining_length_mm: int = Field(gt=0)
    location_id: UUID
    state: ReelState = ReelState.UNOPENED
    verification_state: VerificationState = VerificationState.PROVISIONAL
    quality_status: QualityStatus = QualityStatus.RELEASED
    net_mass_kg: Decimal | None = Field(default=None, ge=0)
    length_confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    parent_reel_id: UUID | None = None
    root_reel_id: UUID | None = None


class ReelResponse(ReelCreate):
    id: UUID
    reservation_id: UUID | None
    handling_count: int
    version: int
    is_fresh: bool
    is_executable: bool


class ReserveRequest(ApiModel):
    reservation_id: UUID
    actor_id: UUID | None = None


class QuarantineRequest(ApiModel):
    reason: str = Field(min_length=1)
    actor_id: UUID | None = None


class VerifyRequest(ApiModel):
    actor_id: UUID | None = None


class MachineCreate(ApiModel):
    code: str = Field(min_length=1)
    min_web_width_mm: int = Field(gt=0)
    max_web_width_mm: int = Field(gt=0)
    min_crosscut_length_mm: int = Field(gt=0)
    max_crosscut_length_mm: int = Field(gt=0)
    min_lane_width_mm: int = Field(gt=0)
    max_lanes: int = Field(gt=0)
    inter_lane_kerf_mm: int = Field(default=0, ge=0)
    min_left_trim_mm: int = Field(default=0, ge=0)
    min_right_trim_mm: int = Field(default=0, ge=0)
    setup_loss_mm: int = Field(default=0, ge=0)
    material_compatibility_groups: frozenset[UUID] = frozenset()


class MachineResponse(MachineCreate):
    id: UUID


class OrderLineCreate(ApiModel):
    sheet_width_mm: int = Field(gt=0)
    sheet_length_mm: int = Field(gt=0)
    quantity_required: int = Field(gt=0)
    quantity_min: int = Field(ge=0)
    quantity_max: int = Field(gt=0)
    material_spec_id: UUID
    due_at: datetime
    earliest_start_at: datetime
    rotation_allowed: bool = False
    grain_requirement: GrainRequirement = GrainRequirement.UNRESTRICTED
    edge_lane_restriction: EdgeLaneRestriction = EdgeLaneRestriction.NONE
    pack_size: int | None = Field(default=None, gt=0)
    split_across_reels_allowed: bool = True
    split_across_days_allowed: bool = True
    early_production_allowed: bool = False
    max_early_days: int | None = Field(default=None, ge=0)
    machine_allowlist: frozenset[UUID] = frozenset()
    machine_denylist: frozenset[UUID] = frozenset()
    recurrence_family_id: UUID | None = None


class OrderCreate(ApiModel):
    customer_id: UUID
    external_id: str = Field(min_length=1)
    received_at: datetime
    promised_at: datetime
    status: OrderStatus = OrderStatus.CONFIRMED
    priority: int = Field(default=100, ge=0)
    service_class: str = "normal"
    contract_id: UUID | None = None
    source_reference: str | None = None
    lines: tuple[OrderLineCreate, ...] = Field(min_length=1)


class OrderLineResponse(OrderLineCreate):
    id: UUID
    order_id: UUID
    version: int


class OrderResponse(ApiModel):
    id: UUID
    customer_id: UUID
    external_id: str
    received_at: datetime
    promised_at: datetime
    status: OrderStatus
    priority: int
    service_class: str
    version: int
    lines: tuple[OrderLineResponse, ...]


class PlanningRequest(ApiModel):
    policy_profile: PolicyName = PolicyName.NORMAL
    mode: str = Field(default="full", pattern="^(full|fast)$")
    time_limit_seconds: int | None = Field(default=None, ge=1, le=3600)
    seed: int = 314159


class ViolationResponse(ApiModel):
    code: str
    message: str
    field: str | None = None
    context: dict[str, Any] | None = None


class PlanRunOutputResponse(ApiModel):
    order_line_id: UUID
    quantity: int


class PlanRunResponse(ApiModel):
    id: UUID
    reel_id: UUID
    reel_segment_id: UUID
    machine_id: UUID
    pattern_id: UUID
    crosscut_count: int
    consumed_length_mm: int
    outputs: tuple[PlanRunOutputResponse, ...]
    sequence: int


class PlanningResponse(ApiModel):
    plan_id: UUID
    snapshot_id: UUID
    snapshot_checksum: str
    status: str
    policy_name: str
    objective: dict[str, int]
    solver: dict[str, Any]
    runs: tuple[PlanRunResponse, ...]
    validation_valid: bool
    violations: tuple[ViolationResponse, ...]
    warnings: tuple[str, ...]
    required_confirmations: tuple[str, ...]


class ErrorResponse(ApiModel):
    code: str
    message: str
    field: str | None = None
    context: dict[str, Any] | None = None


class SimulationRequest(ApiModel):
    scenarios: int = Field(default=100, ge=1, le=10_000)
    seed: int = 314159
    length_error_fraction: Decimal = Field(default=Decimal("0.02"), ge=0, lt=1)
    machine_failure_probability_per_run: Decimal = Field(
        default=Decimal("0.01"), ge=0, le=1
    )


class SimulationOutcomeResponse(ApiModel):
    scenario_index: int
    completed: bool
    failed_run_count: int
    projected_consumed_length_mm: int
    simulated_consumed_length_mm: int
    service_shortage_sheets: int


class SimulationResponse(ApiModel):
    plan_id: UUID
    scenario_count: int
    completion_probability: Decimal
    outcomes: tuple[SimulationOutcomeResponse, ...]


class ReconciliationRequest(ApiModel):
    run_id: UUID
    input_mass_kg: Decimal = Field(gt=0)
    good_product_mass_kg: Decimal = Field(ge=0)
    retained_remainder_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    normal_trim_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    damaged_edge_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    defect_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    setup_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    tail_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    overrun_waste_mass_kg: Decimal = Field(default=Decimal("0"), ge=0)
    tolerance_fraction: Decimal = Field(default=Decimal("0.005"), ge=0, le=1)


class ReconciliationResponse(ApiModel):
    run_id: UUID
    accounted_mass_kg: Decimal
    variance_mass_kg: Decimal
    variance_fraction: Decimal
    within_tolerance: bool