from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from paperbrain.domain.enums import PlanningRunStatus


@dataclass(frozen=True, slots=True)
class PlanRunOutput:
    order_line_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class PlanRun:
    reel_id: UUID
    reel_segment_id: UUID
    machine_id: UUID
    pattern_id: UUID
    crosscut_count: int
    consumed_length_mm: int
    outputs: tuple[PlanRunOutput, ...]
    sequence: int
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.crosscut_count <= 0 or self.consumed_length_mm <= 0:
            raise ValueError("Plan run count and consumed length must be positive")
        if self.sequence < 0:
            raise ValueError("Plan run sequence cannot be negative")
        output_ids = [item.order_line_id for item in self.outputs]
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("Plan run outputs must contain one row per order line")
        if any(item.quantity <= 0 for item in self.outputs):
            raise ValueError("Plan run output quantities must be positive")


@dataclass(frozen=True, slots=True)
class ObjectiveBreakdown:
    service_shortage_sheets: int = 0
    late_seconds: int = 0
    material_loss_minor: int = 0
    trim_area_mm2: int = 0
    fresh_reels_opened: int = 0
    patterns_activated: int = 0
    setup_seconds: int = 0
    stability_penalty_minor: int = 0
    risk_penalty_minor: int = 0


@dataclass(frozen=True, slots=True)
class SolverMetadata:
    name: str
    version: str
    wall_seconds: Decimal
    seed: int
    best_bound: Decimal | None = None
    relative_gap: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Plan:
    snapshot_id: UUID
    policy_name: str
    runs: tuple[PlanRun, ...]
    objective: ObjectiveBreakdown
    status: PlanningRunStatus
    solver: SolverMetadata
    warnings: tuple[str, ...] = ()
    required_confirmations: tuple[str, ...] = ()
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        sequences = [run.sequence for run in self.runs]
        if len(sequences) != len(set(sequences)):
            raise ValueError("Plan run sequences must be unique")

    @property
    def production(self) -> dict[UUID, int]:
        result: dict[UUID, int] = {}
        for run in self.runs:
            for output in run.outputs:
                result[output.order_line_id] = result.get(output.order_line_id, 0) + output.quantity
        return result