from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from paperbrain.domain.enums import (
    MeasurementMethod,
    QualityStatus,
    ReelState,
    VerificationState,
)
from paperbrain.domain.errors import DomainError, DomainViolation

AVAILABLE_STATES = {ReelState.UNOPENED, ReelState.OPENED}
TERMINAL_STATES = {
    ReelState.EXHAUSTED,
    ReelState.SPLIT,
    ReelState.MISSING,
    ReelState.SCRAPPED,
}


@dataclass(frozen=True, slots=True)
class ReelSegment:
    reel_id: UUID
    start_length_mm: int
    end_length_mm: int
    left_unusable_mm: int = 0
    right_unusable_mm: int = 0
    mandatory_left_trim_mm: int = 0
    mandatory_right_trim_mm: int = 0
    confidence: Decimal = Decimal("1")
    inspection_verified: bool = True
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        numeric = (
            self.start_length_mm,
            self.end_length_mm,
            self.left_unusable_mm,
            self.right_unusable_mm,
            self.mandatory_left_trim_mm,
            self.mandatory_right_trim_mm,
        )
        if any(value < 0 for value in numeric) or self.end_length_mm <= self.start_length_mm:
            raise DomainError(DomainViolation("INVALID_REEL_SEGMENT", "Invalid reel segment geometry"))
        if not (Decimal("0") <= self.confidence <= Decimal("1")):
            raise DomainError(DomainViolation("INVALID_CONFIDENCE", "Confidence must be in [0, 1]"))

    @property
    def length_mm(self) -> int:
        return self.end_length_mm - self.start_length_mm

    def usable_width_mm(self, nominal_width_mm: int) -> int:
        unusable = (
            self.left_unusable_mm
            + self.right_unusable_mm
            + self.mandatory_left_trim_mm
            + self.mandatory_right_trim_mm
        )
        return nominal_width_mm - unusable

    def usable_interval(self, nominal_width_mm: int) -> tuple[int, int]:
        start = self.left_unusable_mm + self.mandatory_left_trim_mm
        end = nominal_width_mm - self.right_unusable_mm - self.mandatory_right_trim_mm
        return start, end


@dataclass(frozen=True, slots=True)
class DefectZone:
    reel_id: UUID
    start_length_mm: int
    end_length_mm: int
    cross_start_mm: int
    cross_end_mm: int
    defect_type: str
    severity: str
    disposition: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if (
            self.start_length_mm < 0
            or self.end_length_mm <= self.start_length_mm
            or self.cross_start_mm < 0
            or self.cross_end_mm <= self.cross_start_mm
        ):
            raise DomainError(DomainViolation("INVALID_DEFECT_ZONE", "Invalid defect geometry"))


@dataclass(frozen=True, slots=True)
class ReelMeasurement:
    reel_id: UUID
    measurement_type: str
    value: Decimal
    canonical_unit: str
    method: MeasurementMethod
    observed_at: datetime
    observed_by: UUID | None
    uncertainty: Decimal = Decimal("0")
    source_reference: str | None = None
    original_value: str | None = None
    original_unit: str | None = None
    verification_state: VerificationState = VerificationState.VERIFIED
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.measurement_type or not self.canonical_unit:
            raise DomainError(DomainViolation("INVALID_MEASUREMENT", "Measurement type and unit are required"))
        if self.uncertainty < 0:
            raise DomainError(DomainViolation("INVALID_UNCERTAINTY", "Uncertainty cannot be negative"))
        if self.observed_at.tzinfo is None:
            raise DomainError(DomainViolation("NAIVE_TIMESTAMP", "Measurement timestamp must be timezone-aware"))


@dataclass(frozen=True, slots=True)
class Reel:
    reel_code: str
    material_spec_id: UUID
    nominal_width_mm: int
    remaining_length_mm: int
    location_id: UUID
    root_reel_id: UUID | None = None
    parent_reel_id: UUID | None = None
    state: ReelState = ReelState.UNOPENED
    verification_state: VerificationState = VerificationState.PROVISIONAL
    quality_status: QualityStatus = QualityStatus.RELEASED
    reservation_id: UUID | None = None
    net_mass_kg: Decimal | None = None
    remaining_length_low_mm: int | None = None
    remaining_length_high_mm: int | None = None
    length_confidence: Decimal = Decimal("0")
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    opened_at: datetime | None = None
    last_used_at: datetime | None = None
    handling_count: int = 0
    version: int = 0
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.reel_code.strip():
            raise DomainError(DomainViolation("INVALID_REEL_CODE", "Reel code is required"))
        if self.nominal_width_mm <= 0:
            raise DomainError(DomainViolation("INVALID_WIDTH", "Nominal width must be positive"))
        if self.remaining_length_mm < 0:
            raise DomainError(DomainViolation("INVALID_LENGTH", "Remaining length cannot be negative"))
        if self.net_mass_kg is not None and self.net_mass_kg < 0:
            raise DomainError(DomainViolation("INVALID_MASS", "Net mass cannot be negative"))
        if not (Decimal("0") <= self.length_confidence <= Decimal("1")):
            raise DomainError(DomainViolation("INVALID_CONFIDENCE", "Confidence must be in [0, 1]"))
        if self.received_at.tzinfo is None:
            raise DomainError(DomainViolation("NAIVE_TIMESTAMP", "Received timestamp must be timezone-aware"))
        if self.root_reel_id is None:
            object.__setattr__(self, "root_reel_id", self.id)
        # An opened reel always carries its opening timestamp; is_fresh relies on it.
        if self.state == ReelState.OPENED and self.opened_at is None:
            object.__setattr__(self, "opened_at", self.received_at)

    @property
    def is_fresh(self) -> bool:
        return self.state == ReelState.UNOPENED and self.opened_at is None

    @property
    def is_executable(self) -> bool:
        return (
            self.verification_state == VerificationState.VERIFIED
            and self.quality_status == QualityStatus.RELEASED
            and self.state in AVAILABLE_STATES
            and self.reservation_id is None
            and self.remaining_length_mm > 0
        )

    def default_segment(self) -> ReelSegment:
        return ReelSegment(reel_id=self.id, start_length_mm=0, end_length_mm=self.remaining_length_mm)

    def with_reservation(self, reservation_id: UUID) -> Reel:
        if not self.is_executable:
            raise DomainError(
                DomainViolation("REEL_NOT_AVAILABLE", "Reel is not available for reservation")
            )
        return replace(
            self,
            state=ReelState.RESERVED,
            reservation_id=reservation_id,
            version=self.version + 1,
        )

    def release_reservation(self) -> Reel:
        if self.state != ReelState.RESERVED or self.reservation_id is None:
            raise DomainError(DomainViolation("REEL_NOT_RESERVED", "Reel is not reserved"))
        return replace(
            self,
            state=ReelState.OPENED if self.opened_at else ReelState.UNOPENED,
            reservation_id=None,
            version=self.version + 1,
        )

    def quarantine(self) -> Reel:
        if self.state in TERMINAL_STATES:
            raise DomainError(DomainViolation("INVALID_STATE_TRANSITION", "Terminal reel cannot be quarantined"))
        return replace(
            self,
            state=ReelState.QUARANTINED,
            verification_state=VerificationState.QUARANTINED,
            reservation_id=None,
            version=self.version + 1,
        )