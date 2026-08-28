from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from uuid import UUID, uuid4

from paperbrain.domain.enums import EdgeLaneRestriction
from paperbrain.domain.errors import DomainError, DomainViolation


@dataclass(frozen=True, slots=True)
class OrientationCandidate:
    order_line_id: UUID
    material_spec_id: UUID
    lane_width_mm: int
    crosscut_length_mm: int
    rotated: bool
    edge_lane_restriction: EdgeLaneRestriction
    quantity_min: int
    quantity_max: int
    machine_ids: frozenset[UUID]
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.lane_width_mm <= 0 or self.crosscut_length_mm <= 0:
            raise DomainError(DomainViolation("INVALID_ORIENTATION", "Orientation dimensions must be positive"))


@dataclass(frozen=True, slots=True)
class LanePlacement:
    orientation_id: UUID
    order_line_id: UUID
    start_mm: int
    width_mm: int
    position: int

    @property
    def end_mm(self) -> int:
        return self.start_mm + self.width_mm


@dataclass(frozen=True, slots=True)
class CuttingPattern:
    machine_id: UUID
    material_spec_id: UUID
    crosscut_length_mm: int
    lanes: tuple[LanePlacement, ...]
    usable_width_mm: int
    left_trim_mm: int
    right_trim_mm: int
    kerf_total_mm: int
    setup_family: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.lanes:
            raise DomainError(DomainViolation("EMPTY_PATTERN", "A cutting pattern needs at least one lane"))
        if self.crosscut_length_mm <= 0 or self.usable_width_mm <= 0:
            raise DomainError(DomainViolation("INVALID_PATTERN", "Pattern dimensions must be positive"))
        if min(self.left_trim_mm, self.right_trim_mm, self.kerf_total_mm) < 0:
            raise DomainError(DomainViolation("INVALID_PATTERN_TRIM", "Pattern allowances cannot be negative"))
        positions = [lane.position for lane in self.lanes]
        if positions != list(range(len(self.lanes))):
            raise DomainError(DomainViolation("INVALID_LANE_ORDER", "Lane positions must be contiguous from zero"))

    @property
    def lane_width_total_mm(self) -> int:
        return sum(lane.width_mm for lane in self.lanes)

    @property
    def used_width_mm(self) -> int:
        return self.lane_width_total_mm + self.kerf_total_mm

    @property
    def production_per_crosscut(self) -> dict[UUID, int]:
        result: dict[UUID, int] = {}
        for lane in self.lanes:
            result[lane.order_line_id] = result.get(lane.order_line_id, 0) + 1
        return result

    @property
    def trim_total_mm(self) -> int:
        return self.left_trim_mm + self.right_trim_mm

    @property
    def signature(self) -> str:
        lane_tokens = sorted(
            f"{lane.order_line_id}:{lane.width_mm}:{lane.position}" for lane in self.lanes
        )
        raw = "|".join(
            [
                str(self.machine_id),
                str(self.material_spec_id),
                str(self.crosscut_length_mm),
                str(self.usable_width_mm),
                str(self.left_trim_mm),
                str(self.right_trim_mm),
                str(self.kerf_total_mm),
                *lane_tokens,
            ]
        )
        return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PatternOption:
    reel_id: UUID
    reel_segment_id: UUID
    pattern: CuttingPattern
    available_length_mm: int
    nominal_width_mm: int
    is_fresh_reel: bool
    setup_loss_mm: int

    @property
    def max_crosscuts(self) -> int:
        remaining = self.available_length_mm - self.setup_loss_mm
        return max(0, remaining // self.pattern.crosscut_length_mm)