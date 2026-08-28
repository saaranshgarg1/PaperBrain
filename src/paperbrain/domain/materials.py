from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from paperbrain.domain.enums import GrainRequirement, QualityStatus
from paperbrain.domain.errors import DomainError, DomainViolation


@dataclass(frozen=True, slots=True)
class MaterialSpec:
    family: str
    grade: str
    compatibility_group_id: UUID
    gsm_value: Decimal | None = None
    gsm_min: Decimal | None = None
    gsm_max: Decimal | None = None
    supplier_id: UUID | None = None
    supplier_grade: str | None = None
    finish: str | None = None
    colour: str | None = None
    coating: str | None = None
    grain_rule: GrainRequirement = GrainRequirement.UNRESTRICTED
    quality_class: QualityStatus = QualityStatus.RELEASED
    cost_minor_per_kg: int = 0
    scrap_credit_minor_per_kg: int = 0
    currency: str = "USD"
    shelf_life_days: int | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.family.strip() or not self.grade.strip():
            raise DomainError(
                DomainViolation("INVALID_MATERIAL", "Material family and grade are required")
            )
        if self.gsm_value is None and (self.gsm_min is None or self.gsm_max is None):
            raise DomainError(
                DomainViolation("MISSING_GSM", "Exact GSM or a complete GSM range is required")
            )
        if self.gsm_value is not None and self.gsm_value <= 0:
            raise DomainError(DomainViolation("INVALID_GSM", "GSM must be positive"))
        if self.gsm_min is not None and self.gsm_max is not None:
            if self.gsm_min <= 0 or self.gsm_min > self.gsm_max:
                raise DomainError(DomainViolation("INVALID_GSM_RANGE", "Invalid GSM range"))
        if self.cost_minor_per_kg < 0 or self.scrap_credit_minor_per_kg < 0:
            raise DomainError(DomainViolation("INVALID_MATERIAL_COST", "Material costs cannot be negative"))
        if len(self.currency) != 3:
            raise DomainError(DomainViolation("INVALID_CURRENCY", "Currency must be a three-letter code"))

    @property
    def planning_gsm(self) -> Decimal:
        if self.gsm_value is not None:
            return self.gsm_value
        assert self.gsm_min is not None and self.gsm_max is not None
        return (self.gsm_min + self.gsm_max) / Decimal("2")


@dataclass(frozen=True, slots=True)
class MaterialSubstitution:
    requested_material_id: UUID
    substitute_material_id: UUID
    valid_from: datetime
    valid_to: datetime | None
    approved_by: UUID
    customer_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def active_at(self, instant: datetime) -> bool:
        return instant >= self.valid_from and (self.valid_to is None or instant < self.valid_to)