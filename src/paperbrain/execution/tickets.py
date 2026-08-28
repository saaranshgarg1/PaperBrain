from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from paperbrain.domain.patterns import CuttingPattern
from paperbrain.domain.plans import Plan, PlanRun


@dataclass(frozen=True, slots=True)
class LaneInstruction:
    position: int
    order_line_id: UUID
    start_mm: int
    width_mm: int


@dataclass(frozen=True, slots=True)
class RunTicket:
    plan_id: UUID
    run_id: UUID
    reel_id: UUID
    machine_id: UUID
    pattern_id: UUID
    crosscut_length_mm: int
    crosscut_count: int
    consumed_length_mm: int
    lanes: tuple[LaneInstruction, ...]


def build_run_ticket(plan: Plan, run: PlanRun, pattern: CuttingPattern) -> RunTicket:
    if run.pattern_id != pattern.id:
        raise ValueError("Run and pattern do not match")
    if run not in plan.runs:
        raise ValueError("Run does not belong to plan")
    return RunTicket(
        plan_id=plan.id,
        run_id=run.id,
        reel_id=run.reel_id,
        machine_id=run.machine_id,
        pattern_id=pattern.id,
        crosscut_length_mm=pattern.crosscut_length_mm,
        crosscut_count=run.crosscut_count,
        consumed_length_mm=run.consumed_length_mm,
        lanes=tuple(
            LaneInstruction(
                position=lane.position,
                order_line_id=lane.order_line_id,
                start_mm=lane.start_mm,
                width_mm=lane.width_mm,
            )
            for lane in pattern.lanes
        ),
    )
