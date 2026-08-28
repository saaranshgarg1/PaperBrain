from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from paperbrain.domain.errors import DomainError, DomainViolation


@dataclass(frozen=True, slots=True)
class MachineCapabilities:
    shared_crosscut_length: bool = True
    lanes_can_stop_independently: bool = False
    supports_mixed_crosscut_lengths: bool = False
    supports_roll_to_roll_slitting: bool = False
    supports_roll_to_sheet: bool = True
    supports_two_stage_route: bool = False

    def __post_init__(self) -> None:
        if self.supports_mixed_crosscut_lengths and not self.lanes_can_stop_independently:
            raise DomainError(
                DomainViolation(
                    "INVALID_MACHINE_CAPABILITY",
                    "Mixed cross-cut lengths require independently controllable lanes",
                )
            )


@dataclass(frozen=True, slots=True)
class Machine:
    code: str
    min_web_width_mm: int
    max_web_width_mm: int
    min_crosscut_length_mm: int
    max_crosscut_length_mm: int
    min_lane_width_mm: int
    max_lanes: int
    inter_lane_kerf_mm: int
    min_left_trim_mm: int
    min_right_trim_mm: int
    capabilities: MachineCapabilities = MachineCapabilities()
    material_compatibility_groups: frozenset[UUID] = frozenset()
    setup_loss_mm: int = 0
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise DomainError(DomainViolation("INVALID_MACHINE_CODE", "Machine code is required"))
        if self.min_web_width_mm <= 0 or self.max_web_width_mm < self.min_web_width_mm:
            raise DomainError(DomainViolation("INVALID_WEB_LIMIT", "Invalid web-width limits"))
        if self.min_crosscut_length_mm <= 0 or self.max_crosscut_length_mm < self.min_crosscut_length_mm:
            raise DomainError(DomainViolation("INVALID_CROSSCUT_LIMIT", "Invalid cross-cut limits"))
        if self.min_lane_width_mm <= 0 or self.max_lanes <= 0:
            raise DomainError(DomainViolation("INVALID_LANE_LIMIT", "Invalid lane limits"))
        if min(
            self.inter_lane_kerf_mm,
            self.min_left_trim_mm,
            self.min_right_trim_mm,
            self.setup_loss_mm,
        ) < 0:
            raise DomainError(DomainViolation("INVALID_MACHINE_ALLOWANCE", "Machine allowances cannot be negative"))